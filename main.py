#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from parser import get_latest_news as get_football_ua_news
from onefootball_parser import get_latest_news as get_onefootball_news
from ai_processor import process_article_for_posting, has_gemini_key
from ai_content_checker import check_content_similarity
from db import (
    get_last_run_time,
    update_last_run_time,
    is_already_posted,
    save_posted,
    cleanup_old_posts,
    now_kiev,
    format_kiev_time,
    to_kiev_time,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG = {
    'POST_TIMEOUT': 30,
    'POST_INTERVAL': 3,
    'CLEANUP_DAYS': 7,
    'WORKING_HOURS': (6, 1),  # 06:00 to 01:00
}

try:
    from telegram_bot import TelegramPosterSync, debug_environment
    TELEGRAM_AVAILABLE = True
except ImportError:
    logger.warning("Модуль telegram_bot.py не найден")
    TELEGRAM_AVAILABLE = False

KIEV_TZ = ZoneInfo("Europe/Kiev")

async def post_with_timeout(poster, article, timeout=CONFIG['POST_TIMEOUT']):
    try:
        async with asyncio.timeout(timeout):
            return await asyncio.to_thread(poster.post_article, article)
    except asyncio.TimeoutError:
        logger.error(f"Таймаут при публикации: {article.get('title', '')[:50]}...")
        return False
    except Exception as e:
        logger.error(f"Ошибка при публикации: {e}")
        return False

async def fetch_news(source_name, fetch_func, since_time):
    try:
        news = await asyncio.to_thread(fetch_func, since_time=since_time)
        if news:
            logger.info(f"{source_name}: найдено {len(news)} новостей")
            for item in news:
                item['source'] = source_name
        return news
    except Exception as e:
        logger.error(f"Ошибка получения новостей {source_name}: {e}")
        return []

async def main():
    logger.info("Запуск бота парсинга и публикации новостей")
    current_time_kiev = now_kiev()
    current_hour = current_time_kiev.hour

    if not (CONFIG['WORKING_HOURS'][0] <= current_hour or current_hour <= CONFIG['WORKING_HOURS'][1]):
        logger.info(f"Вне рабочего времени ({current_hour}:00). Завершение.")
        return

    last_run_time = get_last_run_time()
    logger.info(f"Последний запуск: {format_kiev_time(last_run_time)}")
    logger.info(f"Текущее время: {format_kiev_time(current_time_kiev)}")

    update_last_run_time()
    cleanup_old_posts(days=CONFIG['CLEANUP_DAYS'])

    logger.info("Gemini API: " + ("включён" if has_gemini_key() else "отключён"))
    telegram_enabled = TELEGRAM_AVAILABLE and debug_environment()
    logger.info(f"Telegram публикация: {'включена' if telegram_enabled else 'отключена'}")

    # Получение новостей
    all_news = []
    sources = [
        ("Football.ua", get_football_ua_news),
        ("OneFootball", get_onefootball_news),
    ]

    for source_name, fetch_func in sources:
        news = await fetch_news(source_name, fetch_func, last_run_time)
        all_news.extend(news)

    if not all_news:
        logger.info("Новостей не найдено")
        return

    sources_stats = {article.get('source', 'Unknown'): 0 for article in all_news}
    for article in all_news:
        sources_stats[article.get('source', 'Unknown')] += 1

    logger.info("Статистика по источникам:")
    for source, count in sources_stats.items():
        logger.info(f"   {source}: {count} новостей")

    # Фильтрация уже опубликованных
    filtered_news = [article for article in all_news if not is_already_posted(article.get('title', ''))]
    if not filtered_news:
        logger.info("Все новости уже опубликованы")
        return

    logger.info(f"К обработке: {len(filtered_news)} уникальных новостей")
    filtered_news.sort(key=lambda x: x.get('publish_time') or datetime.min.replace(tzinfo=KIEV_TZ), reverse=True)

    # Обработка новостей
    processed_articles = await asyncio.gather(
        *[asyncio.to_thread(process_article_for_posting, article) for article in filtered_news],
        return_exceptions=True
    )

    valid_articles = [result for result in processed_articles if not isinstance(result, Exception)]
    for i, result in enumerate(valid_articles, 1):
        logger.info(f"Обработано [{result.get('source')}]: {result.get('title', '')[:50]}...")

    # Проверка на дубликаты за сегодня
    today_start = current_time_kiev.replace(hour=0, minute=0, second=0, microsecond=0)
    articles_to_publish = [
        article for article in valid_articles
        if not check_content_similarity(article, threshold=0.7, since_time=today_start)
    ]

    if telegram_enabled and articles_to_publish:
        logger.info("Публикация в Telegram")
        try:
            poster = TelegramPosterSync()
            if poster.test_connection():
                successful_posts = 0
                for i, article in enumerate(articles_to_publish):
                    logger.info(f"Публикуем [{article.get('source')}]: {article.get('title', '')[:50]}...")
                    if await post_with_timeout(poster, article):
                        successful_posts += 1
                        save_posted(article.get('title', ''))
                        logger.info("Успешно опубликовано")
                    if i < len(articles_to_publish) - 1:
                        await asyncio.sleep(CONFIG['POST_INTERVAL'])
                logger.info(f"Опубликовано: {successful_posts}/{len(articles_to_publish)}")
            else:
                logger.error("Не удалось подключиться к Telegram")
        except Exception as e:
            logger.error(f"Ошибка публикации: {e}")
    else:
        logger.info("Публикация отключена или нет новостей для публикации")

    # Сохранение результатов
    output_data = {
        'timestamp': current_time_kiev.isoformat(),
        'last_run_time': last_run_time.isoformat() if last_run_time else None,
        'sources_found': sources_stats,
        'total_new_articles': len(filtered_news),
        'total_processed': len(valid_articles),
        'articles_to_publish': len(articles_to_publish) if telegram_enabled else 0,
    }
    try:
        import json
        with open('processed_news.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        logger.info("Результаты сохранены")
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

    logger.info(f"Завершено: обработано {len(valid_articles)}, опубликовано {len(articles_to_publish)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановлено пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
