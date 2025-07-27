
from telegram import Bot
import asyncio
import os

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

async def post_to_telegram(message: str):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHANNEL_ID, text=message)

# Позволяет запускать из обычного кода
def send_message(message: str):
    asyncio.run(post_to_telegram(message))

