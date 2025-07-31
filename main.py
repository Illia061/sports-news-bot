#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from datetime import datetime
from parser import get_latest_news
from ai_processor import process_article_for_posting, has_gemini_key
from content_checker import check_content_similarity
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
    print(f"🕐 Время запуска: {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}")
    print("=" * 70)
    
    # Проверяем настройки
    print("🔧 Проверка конфигурации...")
    
    # Gemini AI
    if has_gemini_key():
        print("✅ Gemini API ключ найден - используем AI резюме")
    else:
        print("⚠️ Gemini API ключ не найден - используем базовые резюме")
    
    # Telegram - подробная проверка
    telegram_enabled = check_telegram_config()
    
    if telegram_enabled:
        print("✅ Telegram настроен - будем публиковать в канал")
    else:
        print("⚠️ Telegram не настроен - только обработка новостей")
    
    print("-" * 70)
    
    # Получаем новости
    print("\n🔍 Получаем новости из блока 'ГОЛОВНЕ ЗА ДОБУ'...")
    news_list = get_latest_news()
    
    if not news_list:
        print("❌ Новости не найдены. Проверьте соединение или структуру сайта.")
        return
    
    print(f"✅ Найдено {len(news_list)} новостей")
    
    # НОВАЯ ЛОГИКА: Берем только ПОСЛЕДНЮЮ новость
    latest_article = news_list[0]  # Самая свежая новость
    print(f"📰 Обрабатываем последнюю новость: {latest_article.get('title', '')[:60]}...")
    
    # Обрабатываем новость
    try:
        processed_article = process_article_for_posting(latest_article)
        print(f"✅ Новость обработана успешно")
        
        if processed_article.get('image_path'):
            print(f"🖼️ Изображение сохранено: {os.path.basename(processed_article['image_path'])}")
        
    except Exception as e:
        print(f"❌ Ошибка обработки: {e}")
        processed_article = {
            'title': latest_article.get('title', ''),
            'post_text': f"⚽ {latest_article.get('title', '')}\n\n#футбол #новини",
            'image_path': '',
            'image_url': latest_article.get('image_url', ''),
            'url': latest_article.get('link', ''),
            'summary': latest_article.get('summary', '')
        }
    
    # Показываем обработанную новость
    print("\n" + "=" * 70)
    print("📰 ОБРАБОТАННАЯ НОВОСТЬ")
    print("=" * 70)
    print("📝 Текст для публикации:")
    print(processed_article.get('post_text', processed_article.get('title', '')))
    
    if processed_article.get('image_path'):
        print(f"🖼️ Изображение: ✅ {os.path.basename(processed_article['image_path'])}")
    elif processed_article.get('image_url'):
        print(f"🖼️ Изображение: 🔗 {processed_article['image_url'][:50]}...")
    else:
        print("🖼️ Изображение: ❌")
    
    print("=" * 70)
    
    # НОВАЯ ЛОГИКА: Проверка на похожесть с недавними постами
    print(f"\n🔍 ПРОВЕРКА НА ДУБЛИКАТЫ")
    print("=" * 70)
    
    try:
        is_duplicate = check_content_similarity(processed_article, threshold=0.7)
        
        if is_duplicate:
            print("🚫 ПРОПУСКАЕМ: Новость слишком похожа на недавно опубликованные")
            print("✅ Работа завершена - дубликат не опубликован")
            return
        else:
            print("✅ УНИКАЛЬНЫЙ КОНТЕНТ: Можно публиковать")
            
    except Exception as e:
        print(f"⚠️ Ошибка проверки дубликатов: {e}")
        print("✅ Продолжаем публикацию (ошибка проверки)")
    
    # Публикация в Telegram
    if telegram_enabled:
        print(f"\n📢 ПУБЛИКАЦИЯ В TELEGRAM")
        print("=" * 70)
        
        try:
            poster = TelegramPosterSync()
            print("🔌 Проверка подключения к Telegram...")
            
            if poster.test_connection():
                print("✅ Подключение успешно!")
                
                print(f"\n🚀 Публикуем новость...")
                success = await post_with_timeout(poster, processed_article)
                
                if success:
                    print(f"✅ УСПЕШНО ОПУБЛИКОВАНО!")
                    
                    # Сохраняем информацию об опубликованной новости
                    try:
                        import json
                        publish_log = {
                            'timestamp': datetime.now().isoformat(),
                            'title': processed_article.get('title', ''),
                            'url': processed_article.get('url', ''),
                            'success': True
                        }
                        
                        # Читаем существующий лог или создаем новый
                        log_file = 'publish_log.json'
                        try:
                            with open(log_file, 'r', encoding='utf-8') as f:
                                log_data = json.load(f)
                                if not isinstance(log_data, list):
                                    log_data = []
                        except:
                            log_data = []
                        
                        # Добавляем новую запись
                        log_data.append(publish_log)
                        
                        # Сохраняем только последние 50 записей
                        log_data = log_data[-50:]
                        
                        with open(log_file, 'w', encoding='utf-8') as f:
                            json.dump(log_data, f, ensure_ascii=False, indent=2)
                        
                        print(f"📝 Запись о публикации сохранена в {log_file}")
                        
                    except Exception as e:
                        print(f"⚠️ Не удалось сохранить лог публикации: {e}")
                        
                else:
                    print(f"❌ НЕ УДАЛОСЬ ОПУБЛИКОВАТЬ")
            else:
                print("❌ Не удалось подключиться к Telegram")
                
        except Exception as e:
            print(f"❌ Ошибка публикации в Telegram: {e}")
            import traceback
            print("🔍 Подробности ошибки:")
            traceback.print_exc()
    
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
            'processed_article': processed_article,
            'telegram_enabled': telegram_enabled,
            'duplicate_check_performed': True
        }
        with open('last_processed_news.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Результаты сохранены в last_processed_news.json")
    except Exception as e:
        print(f"⚠️ Не удалось сохранить результаты: {e}")
    
    # Статистика
    print(f"\n📊 ФИНАЛЬНАЯ СТАТИСТИКА:")
    print(f"   📰 Обработана последняя новость из блока 'ГОЛОВНЕ ЗА ДОБУ'")
    print(f"   🔍 Проверка на дубликаты: Выполнена")
    print(f"   🖼️ Изображение: {'Да' if processed_article.get('image_path') or processed_article.get('image_url') else 'Нет'}")
    print(f"   🤖 AI резюме: {'Да' if has_gemini_key() else 'Нет'}")
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
