
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from parser import get_latest_news
from ai_processor import process_article_for_posting, has_openai_key

def main():
    print("🚀 Запуск бота парсингу новин Football.ua")
    print("=" * 60)
    
    # Проверяем наличие OpenAI API ключа
    if has_openai_key():
        print("✅ OpenAI API ключ знайдено - використовуємо AI резюме")
    else:
        print("⚠️  OpenAI API ключ не знайдено - використовуємо базові резюме")
    
    # Получаем новости
    print("\n🔍 Отримуємо останні новини...")
    news_list = get_latest_news()
    
    if not news_list:
        print("❌ Новини не знайдено. Перевірте з'єднання або структуру сайту.")
        return
    
    print(f"✅ Знайдено {len(news_list)} новин для обробки")
    
    # Обрабатываем каждую новость
    processed_articles = []
    
    for i, article in enumerate(news_list, 1):
        print(f"\n📖 Обробляємо новину {i}/{len(news_list)}...")
        print(f"   Заголовок: {article.get('title', '')[:50]}...")
        
        try:
            # Полная обработка статьи
            processed_article = process_article_for_posting(article)
            processed_articles.append(processed_article)
            
            print(f"✅ Успішно оброблено")
            if processed_article['image_path']:
                print(f"🖼️  Зображення збережено: {processed_article['image_path']}")
            
        except Exception as e:
            print(f"❌ Помилка обробки: {e}")
            # Добавляем базовую версию при ошибке
            processed_articles.append({
                'title': article.get('title', ''),
                'post_text': f"⚽ {article.get('title', '')}\n\n#футбол #новини",
                'image_path': '',
                'image_url': article.get('image_url', ''),
                'url': article.get('link', ''),
                'summary': article.get('summary', '')
            })
    
    # Выводим результаты
    print("\n" + "=" * 60)
    print("📰 ОБРОБЛЕНІ ФУТБОЛЬНІ НОВИНИ")
    print("=" * 60)
    
    for i, article in enumerate(processed_articles, 1):
        print(f"\n📌 НОВИНА {i}")
        print("-" * 40)
        print(f"📝 Текст для публікації:")
        print(article['post_text'])
        
        if article['image_path']:
            print(f"🖼️  Зображення: {article['image_path']}")
        elif article['image_url']:
            print(f"🖼️  Зображення (URL): {article['image_url']}")
        else:
            print("🚫 Зображення відсутнє")
        
        print(f"🔗 Джерело: {article['url']}")
        print("=" * 60)
    
    # Статистика
    print(f"\n📊 СТАТИСТИКА:")
    print(f"   📰 Всього новин: {len(processed_articles)}")
    print(f"   🖼️  З зображеннями: {sum(1 for a in processed_articles if a['image_path'])}")
    print(f"   🤖 З AI резюме: {'Так' if has_openai_key() else 'Ні'}")
    
    # Сохраняем результаты в файл для дальнейшего использования
    try:
        import json
        
        output_data = {
            'timestamp': str(datetime.now()),
            'total_articles': len(processed_articles),
            'articles': processed_articles
        }
        
        with open('processed_news.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Результати збережено в processed_news.json")
        
    except Exception as e:
        print(f"⚠️  Не вдалося зберегти результати: {e}")
    
    print("\n✅ Обробка завершена!")

def cleanup_old_images():
    """Очистка старых изображений"""
    try:
        import os
        import time
        
        images_dir = "images"
        if not os.path.exists(images_dir):
            return
        
        current_time = time.time()
        deleted_count = 0
        
        for filename in os.listdir(images_dir):
            filepath = os.path.join(images_dir, filename)
            if os.path.isfile(filepath):
                # Удаляем файлы старше 24 часов
                if current_time - os.path.getctime(filepath) > 24 * 3600:
                    os.remove(filepath)
                    deleted_count += 1
        
        if deleted_count > 0:
            print(f"🗑️  Видалено {deleted_count} старих зображень")
            
    except Exception as e:
        print(f"⚠️  Помилка очищення зображень: {e}")

if __name__ == "__main__":
    try:
        # Очищаем старые изображения перед началом
        cleanup_old_images()
        
        # Импортируем datetime для статистики
        from datetime import datetime
        
        # Запускаем основную программу
        main()
        
    except KeyboardInterrupt:
        print("\n⏹️  Програма зупинена користувачем")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Критична помилка: {e}")
        sys.exit(1)
