
from parser import get_latest_news
from ai_processor import summarize_news
from db import is_already_posted, save_posted
from telegram_bot import send_message
import time

def main():
    print("Бот стартовал")  # Отладка
    news_list = get_latest_news()
    print(f"Найдено новостей: {len(news_list)}")  # Сколько новостей спарсилось
    for news in news_list:
        if not is_already_posted(news["title"]):
            print(f"Обрабатываем новость: {news['title']}")
            summary = summarize_news(news["title"], news["link"])
            post_text = f"<b>{news['title']}</b>\n\n{summary}\n\n🔗 {news['link']}"
            send_message(post_text)
            save_posted(news["title"])
            print("Новость отправлена и сохранена")
            time.sleep(5)
        else:
            print("Уже публиковали:", news["title"])
    print("Бот завершил работу")  # Отладка

if __name__ == "__main__":
    main()

