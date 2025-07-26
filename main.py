
from parser import get_latest_news
from ai_processor import summarize_news
from db import is_already_posted, save_posted
from telegram_bot import post_to_telegram
import time

def main():
    news_list = get_latest_news()
    for news in news_list:
        if not is_already_posted(news["title"]):
            summary = summarize_news(news["title"], news["link"])
            post_text = f"<b>{news['title']}</b>\n\n{summary}\n\n🔗 {news['link']}"
            post_to_telegram(post_text)
            save_posted(news["title"])
            time.sleep(5)
        else:
            print("Уже публиковали:", news["title"])

if __name__ == "__main__":
    main()
