
from telegram import Bot
import os

bot = Bot(token=os.getenv('8454330473:AAFh0heBBs1NhfKlVUQH7IUbcUdIBpOcf9o'))

def post_to_telegram(text):
    chat_id = os.getenv('@fasterfootballnews')
    bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
