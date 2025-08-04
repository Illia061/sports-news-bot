#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio
import logging
from parser import get_latest_news
from ai_processor import process_article_for_posting, has_gemini_key
from ai_content_checker import check_content_similarity
from db import get_last_run_time, update_last_run_time, is_already_posted, save_posted, cleanup_old_posts, debug_db_state, now_kiev, format_kiev_time, to_kiev_time

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация
CONFIG = {
    'POST_TIMEOUT': 30,
    'POST_INTERVAL': 3,
    'CLEANUP_DAYS': 7,
    'WORKING_HOURS': (6, 1)  # с 06:00 до 01:00
}

# Импортируем модули
try:
    from telegram_bot import TelegramPosterSync, debug_environment
    TELEGRAM_AVAILABLE = True
except ImportError:
    logger.warning("Модуль telegram_bot.py не найден")
    TELEGRAM_AVAILABLE = False

KIEV_TZ = ZoneInfo("Europe/Kiev")

def check_telegram_config():
    """Проверяет настройки Telegram."""
    if not TELEGRAM_AVAILABLE:
        logger.error("Модуль Telegram недоступен")
        return False
    logger.info("Проверка Telegram настроек")
    return debug_environment()

async def post_with_timeout(poster, article, timeout=CONFIG['POST_TIMEOUT']):
    """Асинхронная публикация статьи с таймаутом."""
    try:
        async with asyncio.timeout(timeout):
            return await asyncio.to_thread(poster.post_article, article)
    except asyncio.TimeoutError:
        logger.error(f"Таймаут при публикации: {article.get('title', '')[:60]}...")
        return False
    except Exception as e:
        logger.error(f"Ошибка при публикации: {e}")
        return False

async def main():
    logger.info("Запуск бота парсинга и публикации новостей Football.ua")
    
    current_time_kiev = now_kiev()
    current_hour = current_time_kiev.hour
    
    if not (CONFIG['WORKING_HOURS'][0] <= current_hour or current_hour <= CONFIG['WORKING_HOURS'][1]):
        logger.info(f"Вне рабочего времени ({current_hour}:00). Завершение работы.")
        return
        
    logger.info("=" * 70)
    
    # Получаем время последнего запуска
    logger.info("Определяем время последнего запуска...")
    last_run_time = get_last_run_time()
    
    logger.info(f"Последний запуск: {format_kiev_time(last_run_time)} (Киев)")
    logger.info(f"Текущее время: {format_kiev_time(current_time_kiev)} (Киев)")
    logger.info(f"Интервал: {(current_time_kiev - to_kiev_time(last_run_time)).total_seconds() / 60:.1f} минут")
    
    debug_db_state()
    filter_time = last_run_time
    update_last_run_time()
    cleanup_old_posts(days=CONFIG['CLEANUP_DAYS'])
    
    # Проверяем настройки
    logger.info("Проверка конфигурации...")
    if has_gemini_key():
        logger.info("Gemini API ключ найден - используем AI резюме и проверку дубликатов")
    else:
        logger.warning("Gemini API ключ не найден - используем базовые резюме")
    
    telegram_enabled = check_telegram_config()
    logger.info(f"Telegram публикация: {'Включена' if telegram_enabled else 'Отключена'}")
    
    logger.info("-" * 70)
    
    # Получаем новости из Football.ua
    all_news = []
    
    logger.info(f"Получаем новости Football.ua с {format_kiev_time(filter_time)} (Киев)...")
    try:
        football_ua_news = await asyncio.to_thread(get_latest_news, since_time=filter_time)
        if football_ua_news:
            logger.info(f"Football.ua: найдено {len(football_ua_news)} новостей")
            for news in football_ua_news:
                news['source'] = 'Football.ua'
            all_news.extend(football_ua_news)
        else:
            logger.info("Football.ua: новостей не найдено")
    except Exception as e:
        logger.error(f"Ошибка получения новостей Football.ua: {e}")
    
    if not all_news:
        logger.info("Новостей не найдено")
        return
    
    logger.info(f"Всего найдено {len(all_news)} новостей")
    
    # Статистика по источникам
    sources_stats = {}
    for article in all_news:
        source = article.get('source', 'Unknown')
        sources_stats[source] = sources_stats.get(source, 0) + 1
    
    logger.info("Статистика по источникам:")
    for source, count in sources_stats.items():
        logger.info(f"   {source}: {count} новостей")
    
    # Фильтрация уже опубликованных
    logger.info("Фильтруем опубликованные новости...")
    filtered_news = [
        article for article in all_news
        if not is_already_posted(article.get('title', ''))
    ]
    
    for article in all_news:
        source = article.get('source', 'Unknown')
        title = article.get('title', '')[:50]
        time_str = format_kiev_time(article.get('publish_time')) if article.get('publish_time') else 'время неизвестно'
        status = 'Новая' if article in filtered_news else 'Уже опубликована'
        logger.info(f"{status} ({source}): {title}... ({time_str})")
    
    if not filtered_news:
        logger.info("Все новости уже были опубликованы")
        return
    
    logger.info(f"К обработке: {len(filtered_news)} уникальных новостей")
    
    # Сортируем по времени публикации
    filtered_news.sort(key=lambda x: x.get('publish_time') or datetime.min.replace(tzinfo=KIEV_TZ), reverse=True)
    
    # Параллельная обработка новостей
    logger.info("Обработка новостей...")
    processed_articles = await asyncio.gather(
        *[asyncio.to_thread(process_article_for_posting, article) for article in filtered_news],
        return_exceptions=True
    )
    
    # Обрабатываем результаты
    valid_articles = []
    for i, result in enumerate(processed_articles, 1):
        if isinstance(result, Exception):
            logger.error(f"Ошибка обработки новости {i}: {result}")
            continue
        valid_articles.append(result)
        source = result.get('source', 'Unknown')
        logger.info(f"Обработано [{source}]: {result.get('title', '')[:50]}...")
        if result.get('image_path'):
            logger.info(f"Изображение сохранено: {os.path.basename(result['image_path'])}")
    
    # Вывод обработанных новостей
    logger.info("=" * 70)
    logger.info("ОБРАБОТАННЫЕ НОВОСТИ")
    logger.info("=" * 70)
    
    for i, article in enumerate(valid_articles, 1):
        source = article.get('source', 'Unknown')
        logger.info(f"НОВОСТЬ {i} [{source}]")
        logger.info("-" * 50)
        logger.info(f"Текст для публикации:\n{article.get('post_text', article.get('title', ''))}")
        
        if article.get('image_path'):
            image_info = f"✅ {os.path.basename(article['image_path'])}"
        elif article.get('image_url'):
            image_info = f"🔗 {article.get('image_url', '')[:50]}..."
        else:
            image_info = "❌"
        
        logger.info(f"Изображение: {image_info}")
        logger.info("=" * 50)
    
    # Инициализируем переменную для scope
    articles_to_publish = []
    
    # Публикация в Telegram
    if telegram_enabled and valid_articles:
        logger.info("ПРОВЕРКА НА ДУБЛИКАТЫ И ПУБЛИКАЦИЯ")
        logger.info("=" * 70)
        
        articles_to_publish = [
            article for article in valid_articles
            if not check_content_similarity(article, threshold=0.7)
        ]
        
        for i, article in enumerate(valid_articles, 1):
            source = article.get('source', 'Unknown')
            title = article.get('title', '')[:50]
            status = 'Уникальный контент' if article in articles_to_publish else 'Дубликат обнаружен'
            logger.info(f"Проверяем новость {i}/{len(valid_articles)} [{source}]: {title}...")
            logger.info(f"{status}")
        
        if articles_to_publish:
            logger.info("ПУБЛИКАЦИЯ В TELEGRAM")
            logger.info("=" * 70)
            
            try:
                poster = TelegramPosterSync()
                if poster.test_connection():
                    logger.info("Подключение к Telegram успешно")
                    
                    successful_posts = 0
                    for i, article in enumerate(articles_to_publish, 1):
                        source = article.get('source', 'Unknown')
                        logger.info(f"Публикуем новость {i}/{len(articles_to_publish)} [{source}]...")
                        if await post_with_timeout(poster, article):
                            successful_posts += 1
                            save_posted(article.get('title', ''))
                            logger.info("Успешно опубликовано")
                        else:
                            logger.error("Не удалось опубликовать")
                        
                        if i < len(articles_to_publish):
                            await asyncio.sleep(CONFIG['POST_INTERVAL'])
                    
                    logger.info(f"ПУБЛИКАЦИЯ ЗАВЕРШЕНА: {successful_posts}/{len(articles_to_publish)} успешно")
                    
                    # Статистика опубликованных
                    published_sources = {}
                    for article in articles_to_publish[:successful_posts]:
                        source = article.get('source', 'Unknown')
                        published_sources[source] = published_sources.get(source, 0) + 1
                    
                    logger.info("Опубликовано по источникам:")
                    for source, count in published_sources.items():
                        logger.info(f"   {source}: {count} новостей")
                else:
                    logger.error("Не удалось подключиться к Telegram")
            except Exception as e:
                logger.error(f"Ошибка публикации в Telegram: {e}", exc_info=True)
        else:
            logger.info("НЕТ НОВОСТЕЙ ДЛЯ ПУБЛИКАЦИИ: все являются дубликатами")
    
    else:
        logger.info("ПУБЛИКАЦИЯ В TELEGRAM ОТКЛЮЧЕНА")
        if not telegram_enabled:
            logger.info("Для включения проверьте переменные окружения и настройки бота")
        if not valid_articles:
            logger.info("Нет обработанных новостей для публикации")
    
    # Сохранение результатов
    try:
        import json
        output_data = {
            'timestamp': current_time_kiev.isoformat(),
            'last_run_time': filter_time.isoformat() if filter_time else None,
            'timezone': 'Europe/Kiev',
            'sources_found': sources_stats,
            'total_new_articles': len(filtered_news),
            'total_processed': len(valid_articles),
            'articles_to_publish': len(articles_to_publish),
            'telegram_enabled': telegram_enabled,
            'articles': valid_articles
        }
        with open('processed_news.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        logger.info("Результаты сохранены в processed_news.json")
    except Exception as e:
        logger.error(f"Не удалось сохранить результаты: {e}")
    
    # Финальная статистика
    logger.info("=" * 70)
    logger.info("ФИНАЛЬНАЯ СТАТИСТИКА")
    logger.info("=" * 70)
    logger.info(f"Фильтр времени: с {format_kiev_time(filter_time)} (Киев)")
    logger.info(f"Найдено новых: {len(all_news)}")
    logger.info("По источникам:")
    for source, count in sources_stats.items():
        logger.info(f"   - {source}: {count}")
    logger.info(f"После фильтрации дубликатов: {len(filtered_news)}")
    logger.info(f"Обработано: {len(valid_articles)}")
    logger.info(f"Проверено на дубликаты: {'Да' if telegram_enabled else 'Нет'}")
    logger.info(f"К публикации: {len(articles_to_publish) if telegram_enabled else 'Неизвестно'}")
    logger.info(f"С изображениями: {sum(1 for a in valid_articles if a.get('image_path') or a.get('image_url'))}")
    logger.info(f"С AI резюме: {'Да' if has_gemini_key() else 'Нет'}")
    logger.info("BeSoccer парсер: Недоступен")
    logger.info(f"Telegram публикация: {'Включена' if telegram_enabled else 'Отключена'}")
    logger.info(f"Время выполнения: {format_kiev_time(current_time_kiev)} (Киев)")
    logger.info("Работа завершена!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа остановлена пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
