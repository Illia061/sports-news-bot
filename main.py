#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from datetime import datetime
from parser import get_latest_news
from ai_processor import process_article_for_posting, has_gemini_key
from ai_content_checker import check_content_similarity
from db import get_last_run_time, update_last_run_time, is_already_posted, save_posted, cleanup_old_posts, debug_db_state
import asyncio

# Импортируем наш Telegram модуль
try:
    from telegram_bot import TelegramPosterSync, debug_environment
    TELEGRAM_AVAILABLE = True
except ImportError:
    print("⚠️ telegram_bot.py не найден")
    TELEGRAM_AVAILABLE = False

def check_telegram_config():
    """Проверяет настройки Telegram"""
    if not TELEGRAM_AVAILABLE:
        print("❌ Telegram модуль недоступен")
        return False
    print("🔧 ПРОВЕРКА TELEGRAM НАСТРОЕК:")
    return debug_environment()

async def post_with_timeout(poster, article, timeout=30):
    """Постинг статьи с таймаутом"""
    try:
        async with asyncio.timeout(timeout):
            return await asyncio.to_thread(poster.post_article, article)
    except asyncio.TimeoutError:
        print(f"❌ Таймаут при публикации: {article.get('title', '')[:60]}...")
        return False
    except Exception as e:
        print(f"❌ Ошибка при публикации: {e}")
        return False

async def main():
    print("🚀 Запуск бота парсинга и публикации новостей Football.ua")
    
    current_hour = datetime.now().hour
    if not (6 <= current_hour or current_hour <= 1):  # с 06:00 до 01:00
        print(f"⏰ Сейчас {current_hour}:00 — вне времени работы. Бот завершает работу.")
        return
        
    print("=" * 70)
    
    # НОВАЯ ЛОГИКА: Получаем время последнего запуска
    print("🕒 Определяем время последнего запуска...")
    last_run_time = get_last_run_time()
    current_time = datetime.now()
    
    print(f"📊 Последний запуск: {last_run_time.strftime('%H:%M %d.%m.%Y')}")
    print(f"📊 Текущее время: {current_time.strftime('%H:%M %d.%m.%Y')}")
    print(f"⏱️  Интервал: {(current_time - last_run_time).total_seconds() / 60:.1f} минут")
    
    # Отладка состояния БД
    debug_db_state()
    
    # Обновляем время запуска в начале (но сохраняем старое для фильтрации)
    filter_time = last_run_time
    update_last_run_time()
    
    # Очищаем старые записи
    cleanup_old_posts(days=7)
    
    # Проверяем настройки
    print("\n🔧 Проверка конфигурации...")
    
    # Gemini
    if has_gemini_key():
        print("✅ Gemini API ключ найден - используем AI резюме и проверку дубликатов")
    else:
        print("⚠️ Gemini API ключ не найден - используем базовые резюме и проверку дубликатов")
    
    # Telegram - подробная проверка
    telegram_enabled = check_telegram_config()
    
    if telegram_enabled:
        print("✅ Telegram настроен - будем публиковать в канал")
    else:
        print("⚠️ Telegram не настроен - только обработка новостей")
    
    print("-" * 70)
    
    # НОВАЯ ЛОГИКА: Получаем только новости с момента последнего запуска
    print(f"\n🔍 Получаем новости с {filter_time.strftime('%H:%M %d.%m.%Y')}...")
    news_list = get_latest_news(since_time=filter_time)
    
    if not news_list:
        print("📭 Новых новостей с момента последнего запуска не найдено.")
        print(f"💡 Проверим снова через 20 минут (следующий запуск)")
        return
    
    print(f"✅ Найдено {len(news_list)} новых новостей для обработки")
    
    # Дополнительная фильтрация: убираем уже опубликованные
    print("\n🔍 Фильтруем уже опубликованные новости...")
    filtered_news = []
    
    for article in news_list:
        title = article.get('title', '')
        if not is_already_posted(title):
            filtered_news.append(article)
            print(f"✅ Новая: {title[:60]}...")
        else:
            print(f"🚫 Уже опубликована: {title[:60]}...")
    
    if not filtered_news:
        print("📭 Все найденные новости уже были опубликованы.")
        return
    
    print(f"✅ К обработке: {len(filtered_news)} уникальных новостей")
    
    # Обрабатываем каждую новость
    print("\n📝 Обработка новостей...")
    processed_articles = []
    
    for i, article in enumerate(filtered_news, 1):
        print(f"\n📖 Обрабатываем новость {i}/{len(filtered_news)}:")
        print(f"   {article.get('title', '')[:60]}...")
        
        try:
            processed_article = process_article_for_posting(article)
            processed_articles.append(processed_article)
            print(f"✅ Обработано успешно")
            if processed_article.get('image_path'):
                print(f"🖼️ Изображение сохранено: {os.path.basename(processed_article['image_path'])}")
        except Exception as e:
            print(f"❌ Ошибка обработки: {e}")
            processed_articles.append({
                'title': article.get('title', ''),
                'post_text': f"⚽ {article.get('title', '')}\n\n#футбол #новини",
                'image_path': '',
                'image_url': article.get('image_url', ''),
                'url': article.get('link', ''),
                'summary': article.get('summary', '')
            })
    
    # Показываем обработанные новости
    print("\n" + "=" * 70)
    print("📰 ОБРАБОТАННЫЕ НОВЫЕ НОВОСТИ")
    print("=" * 70)
    
    for i, article in enumerate(processed_articles, 1):
        print(f"\n📌 НОВОСТЬ {i}")
        print("-" * 50)
        print("📝 Текст для публикации:")
        print(article.get('post_text', article.get('title', '')))
        
        if article.get('image_path'):
            print(f"🖼️ Изображение: ✅ {os.path.basename(article['image_path'])}")
        elif article.get('image_url'):
            print(f"🖼️ Изображение: 🔗 {article['image_url'][:50]}...")
        else:
            print("🖼️ Изображение: ❌")
        
        print("=" * 50)
    
    # ИЗМЕНЕННАЯ ЛОГИКА: Проверяем все новые статьи на дубликаты и публикуем их
    if telegram_enabled and processed_articles:
        print(f"\n🔍 ПРОВЕРКА НА ДУБЛИКАТЫ И ПУБЛИКАЦИЯ")
        print("=" * 70)
        
        articles_to_publish = []
        
        # Проверяем каждую новую новость на дубликаты
        for i, article in enumerate(processed_articles, 1):
            print(f"\n📊 Проверяем новость {i}/{len(processed_articles)} на дубликаты...")
            print(f"   📰 {article.get('title', '')[:60]}...")
            
            # Проверяем на дубликаты
            is_duplicate = check_content_similarity(article, threshold=0.7)
            
            if is_duplicate:
                print(f"🚫 ДУБЛІКАТ ОБНАРУЖЕН - пропускаем публикацию")
            else:
                print(f"✅ УНИКАЛЬНЫЙ КОНТЕНТ - добавляем к публикации")
                articles_to_publish.append(article)
        
        # Публикация в Telegram
        if articles_to_publish:
            print(f"\n📢 ПУБЛИКАЦИЯ В TELEGRAM")
            print("=" * 70)
            
            try:
                poster = TelegramPosterSync()
                print("🔌 Проверка подключения к Telegram...")
                if poster.test_connection():
                    print("✅ Подключение успешно!")
                    
                    print(f"\n🚀 Начинаем публикацию {len(articles_to_publish)} новостей...")
                    successful_posts = 0
                    
                    for i, article in enumerate(articles_to_publish, 1):
                        print(f"\n📤 Публикуем новость {i}/{len(articles_to_publish)}...")
                        if await post_with_timeout(poster, article):
                            successful_posts += 1
                            print(f"✅ Успешно опубликовано")
                            
                            # Сохраняем информацию об опубликованной новости
                            title = article.get('title', '')
                            if title:
                                save_posted(title)
                                print(f"💾 Сохранена запись о публикации: {title[:50]}...")
                        else:
                            print(f"❌ Не удалось опубликовать")
                        
                        # Задержка между постами
                        if i < len(articles_to_publish):
                            await asyncio.sleep(3)
                    
                    print(f"\n🎉 ПУБЛИКАЦИЯ ЗАВЕРШЕНА!")
                    print(f"✅ Успешно опубликовано: {successful_posts}/{len(articles_to_publish)}")
                    
                    if successful_posts < len(articles_to_publish):
                        print(f"❌ Не удалось опубликовать: {len(articles_to_publish) - successful_posts}")
                else:
                    print("❌ Не удалось подключиться к Telegram")
                    
            except Exception as e:
                print(f"❌ Ошибка публикации в Telegram: {e}")
                import traceback
                print("🔍 Подробности ошибки:")
                traceback.print_exc()
        else:
            print(f"\n🚫 НЕТ НОВОСТЕЙ ДЛЯ ПУБЛИКАЦИИ")
            print("📋 Все новые новости оказались дубликатами последних постов в канале")
    
    elif not telegram_enabled:
        print(f"\n📢 ПУБЛИКАЦИЯ В TELEGRAM ОТКЛЮЧЕНА")
        print("📋 Для включения:")
        print("1. Убедитесь что переменные добавлены на Railway:")
        print("   - TELEGRAM_BOT_TOKEN")
        print("   - TELEGRAM_CHANNEL_ID")
        print("2. Перезапустите деплой на Railway")
        print("3. Проверьте что бот добавлен в канал как админ")
    
    # Сохраняем результаты
    try:
        import json
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'last_run_time': filter_time.isoformat(),
            'total_new_articles': len(filtered_news),
            'total_processed': len(processed_articles),
            'articles_to_publish': len(articles_to_publish) if telegram_enabled and 'articles_to_publish' in locals() else 0,
            'telegram_enabled': telegram_enabled,
            'articles': processed_articles
        }
        with open('processed_news.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Результаты сохранены в processed_news.json")
    except Exception as e:
        print(f"⚠️ Не удалось сохранить результаты: {e}")
    
    # Статистика
    print(f"\n📊 ФИНАЛЬНАЯ СТАТИСТИКА:")
    print(f"   🕒 Фильтр времени: с {filter_time.strftime('%H:%M %d.%m')}")
    print(f"   📰 Найдено новых: {len(news_list)}")
    print(f"   🔍 После фильтрации дубликатов БД: {len(filtered_news)}")
    print(f"   📝 Обработано: {len(processed_articles)}")
    print(f"   🔍 Проверено на дубликаты контента: {'Да' if telegram_enabled else 'Нет'}")
    print(f"   📢 К публикации: {len(articles_to_publish) if telegram_enabled and 'articles_to_publish' in locals() else 'Неизвестно'}")
    print(f"   🖼️ С изображениями: {sum(1 for a in processed_articles if a.get('image_path') or a.get('image_url'))}")
    print(f"   🤖 С AI резюме: {'Да' if has_gemini_key() else 'Нет'}")
    print(f"   📢 Telegram публикация: {'Включена' if telegram_enabled else 'Отключена'}")
    
    print(f"\n✅ Работа завершена!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Программа остановлена пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
