import os
import sys
from datetime import datetime
from parser import get_latest_news
from ai_processor import process_article_for_posting, has_openai_key

try:
    from telegram_poster import TelegramPosterSync
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

def main():
    print("\n🚀 Запуск новостного бота")

    news_list = get_latest_news()
    if not news_list:
        print("❌ Новости не найдены")
        return

    print(f"✅ Найдено {len(news_list)} новостей")

    processed_articles = []
    for article in news_list:
        try:
            processed_article = process_article_for_posting(article)
        except Exception:
            processed_article = {
                'title': article.get('title', ''),
                'post_text': article.get('title', ''),
                'image_path': '',
                'image_url': article.get('image_url', ''),
                'url': article.get('link', ''),
                'summary': article.get('summary', '')
            }
        processed_articles.append(processed_article)

    if TELEGRAM_AVAILABLE:
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        channel_id = os.getenv('TELEGRAM_CHANNEL_ID')

        if bot_token and channel_id:
            try:
                poster = TelegramPosterSync()
                if poster.test_connection():
                    poster.post_articles(processed_articles, delay=3)
                    print("✅ Новости отправлены в Telegram")
                else:
                    print("❌ Не удалось подключиться к Telegram")
            except Exception as e:
                print(f"❌ Ошибка Telegram: {e}")
        else:
            print("⚠️  Отсутствуют TELEGRAM_BOT_TOKEN или TELEGRAM_CHANNEL_ID")
    else:
        print("⚠️  telegram_poster.py не найден - Telegram отключен")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"💥 Ошибка выполнения: {e}")
        sys.exit(1)
