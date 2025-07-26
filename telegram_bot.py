
from telegram import Bot
import os

bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))

def post_to_telegram(text):
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID")
    bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
