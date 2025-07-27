#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from datetime import datetime
from parser import get_latest_news
from ai_processor import process_article_for_posting, has_openai_key

# Импортируем Telegram постер
try:
    from telegram_poster import TelegramPosterSync
    TELEGRAM_AVAILABLE = True
except ImportError:
    print("⚠️  telegram_poster.py не найден. Публикация в Telegram недоступна.")
    TELEGRAM_AVAILABLE = False

def check_telegram_config():
    """Проверяет настройки Telegram"""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
    
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN не найден")
        print("   Установите: export TELEGRAM_BOT_TOKEN='ваш_токен_бота'")
        return False
    
    if not channel_id:
        print("❌ TELEGRAM_CHANNEL_ID не найден") 
        print("   Установите: export TELEGRAM_CHANNEL_ID='@ваш_канал'")
        return False
    
    return True

def main():
    print("🚀 Запуск бота парсинга и публикации новостей Football.ua")
    print("=" * 70)
    
    # Проверяем настройки
    print("🔧 Проверка конфигурации...")
    
    # OpenAI
    if has_openai_key():
        print("✅ OpenAI API ключ найден - используем AI резюме")
    else:
        print("⚠️  OpenAI API ключ не найден - используем базовые резюме")
    
    # Telegram
    telegram_enabled = False
    if TELEGRAM_AVAILABLE:
        if check_telegram_config():
            print("✅ Telegram настроен - будем публиковать в канал")
            telegram_enabled = True
        else:
            print("⚠️  Telegram не настроен - только обработка новостей")
    else:
        print("⚠️  Telegram модуль недоступен - только обработка новостей")
    
    print("-" * 70)
    
    # Получаем новости
    print("\n🔍 Получаем новости из блока 'ГОЛОВНЕ ЗА ДОБУ'...")
    news_list = get_latest_news()
    
    if not news_list:
        print("❌ Новости не найдены. Проверьте соединение или структуру сайта.")
        return
    
    print(f"✅ Найдено {len(news_list)} новостей для обработки")
    
    # Обрабатываем каждую новость
    print("\n📝 Обработка новостей...")
    processed_articles = []
    
    for i, article in enumerate(news_list, 1):
        print(f"\n📖 Обрабатываем новость {i}/{len(news_list)}:")
        print(f"   {article.get('title', '')[:60]}...")
        
        try:
            # Полная обработка статьи
            processed_article = process_article_for_posting(article)
            processed_articles.append(processed_article)
            
            print(f"✅ Обработано успешно")
            if processed_article['image_path']:
                print(f"🖼️  Изображение сохранено: {os.path.basename(processed_article['image_path'])}")
            
        except Exception as e:
            print(f"❌ Ошибка обработки: {e}")
            # Добавляем базовую версию при ошибке
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
    print("📰 ОБРАБОТАННЫЕ НОВОСТИ")
    print("=" * 70)
    
    for i, article in enumerate(processed_articles, 1):
        print(f"\n📌 НОВОСТЬ {i}")
        print("-" * 50)
        print("📝 Текст для публикации:")
        print(article['post_text'])
        
        if article['image_path']:
            print(f"🖼️  Изображение: ✅ {os.path.basename(article['image_path'])}")
        elif article['image_url']:
            print(f"🖼️  Изображение: 🔗 {article['image_url'][:50]}...")
        else:
            print("🖼️  Изображение: ❌")
        
        print("=" * 50)
    
    # Публикация в Telegram
    if telegram_enabled and processed_articles:
        print(f"\n📢 ПУБЛИКАЦИЯ В TELEGRAM")
        print("=" * 70)
        
        try:
            poster = TelegramPosterSync()
            
            # Тестируем подключение
            print("🔌 Проверка подключения к Telegram...")
            if poster.test_connection():
                print("✅ Подключение успешно!")
                
                # Спрашиваем подтверждение
                print(f"\n❓ Опубликовать {len(processed_articles)} новостей в канал?")
                print("   Введите 'да' или 'yes' для подтверждения, любой другой ввод для отмены:")
                
                user_input = input("   Ваш выбор: ").lower().strip()
                
                if user_input in ['да', 'yes', 'y', 'д']:
                    print(f"\n🚀 Начинаем публикацию...")
                    
                    # Публикуем с задержкой в 3 секунды между постами
                    successful_posts = poster.post_articles(processed_articles, delay=3)
                    
                    print(f"\n🎉 ПУБЛИКАЦИЯ ЗАВЕРШЕНА!")
                    print(f"✅ Успешно опубликовано: {successful_posts}/{len(processed_articles)}")
                    
                    if successful_posts < len(processed_articles):
                        print(f"❌ Не удалось опубликовать: {len(processed_articles) - successful_posts}")
                else:
                    print("⏹️  Публикация отменена пользователем")
            else:
                print("❌ Не удалось подключиться к Telegram")
                
        except Exception as e:
            print(f"❌ Ошибка публикации в Telegram: {e}")
    
    elif not telegram_enabled:
        print(f"\n📢 ПУБЛИКАЦИЯ В TELEGRAM ОТКЛЮЧЕНА")
        print("Для включения настройте переменные окружения:")
        print("export TELEGRAM_BOT_TOKEN='ваш_токен'")
        print("export TELEGRAM_CHANNEL_ID='@ваш_канал'")
    
    # Сохраняем результаты
    try:
        import json
        
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'total_articles': len(processed_articles),
            'telegram_enabled': telegram_enabled,
            'articles': processed_articles
        }
        
        with open('processed_news.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Результаты сохранены в processed_news.json")
        
    except Exception as e:
        print(f"⚠️  Не удалось сохранить результаты: {e}")
    
    # Статистика
    print(f"\n📊 ФИНАЛЬНАЯ СТАТИСТИКА:")
    print(f"   📰 Обработано новостей: {len(processed_articles)}")
    print(f"   🖼️  С изображениями: {sum(1 for a in processed_articles if a['image_path'] or a['image_url'])}")
    print(f"   🤖 С AI резюме: {'Да' if has_openai_key() else 'Нет'}")
    print(f"   📢 Telegram публикация: {'Включена' if telegram_enabled else 'Отключена'}")
    
    print(f"\n✅ Работа завершена!")

def cleanup_old_files():
    """Очистка старых файлов"""
    try:
        import glob
        import time
        
        # Очищаем старые изображения
        images_dir = "images"
        if os.path.exists(images_dir):
            current_time = time.time()
            deleted_count = 0
            
            for filepath in glob.glob(os.path.join(images_dir, "*")):
                if os.path.isfile(filepath):
                    # Удаляем файлы старше 48 часов
                    if current_time - os.path.getctime(filepath) > 48 * 3600:
                        os.remove(filepath)
                        deleted_count += 1
            
            if deleted_count > 0:
                print(f"🗑️  Удалено {deleted_count} старых изображений")
        
        # Очищаем старые JSON файлы
        for old_json in glob.glob("processed_news_*.json"):
            try:
                file_time = os.path.getctime(old_json)
                if time.time() - file_time > 7 * 24 * 3600:  # 7 дней
                    os.remove(old_json)
            except:
                pass
                
    except Exception as e:
        print(f"⚠️  Ошибка очистки файлов: {e}")

if __name__ == "__main__":
    try:
        # Очищаем старые файлы
        cleanup_old_files()
        
        # Запускаем основную программу
        main()
        
    except KeyboardInterrupt:
        print("\n⏹️  Программа остановлена пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
