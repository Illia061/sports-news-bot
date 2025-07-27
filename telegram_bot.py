
import os
import asyncio
import aiohttp
from typing import List, Dict, Any
import json
from urllib.parse import urlparse

class TelegramPoster:
    def __init__(self, bot_token: str = None, channel_id: str = None):
        # Добавляем отладочную информацию
        print("🔍 ОТЛАДКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ:")
        print(f"Bot token из параметра: {'Есть' if bot_token else 'Нет'}")
        print(f"Channel ID из параметра: {'Есть' if channel_id else 'Нет'}")
        
        # Получаем из переменных окружения
        env_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        env_channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
        
        print(f"Bot token из env: {'Есть (' + env_bot_token[:10] + '...)' if env_bot_token else 'НЕТ!'}")
        print(f"Channel ID из env: {env_channel_id if env_channel_id else 'НЕТ!'}")
        
        # Показываем все переменные окружения (для отладки)
        print("\n📋 ВСЕ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ:")
        for key, value in os.environ.items():
            if 'TELEGRAM' in key.upper():
                print(f"  {key} = {value[:20] + '...' if len(value) > 20 else value}")
        
        self.bot_token = bot_token or env_bot_token
        self.channel_id = channel_id or env_channel_id
        
        if self.bot_token:
            self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        print(f"\n✅ Итоговые значения:")
        print(f"Bot token: {'Установлен' if self.bot_token else 'НЕТ!'}")
        print(f"Channel ID: {self.channel_id if self.channel_id else 'НЕТ!'}")
        print("=" * 50)
        
        if not self.bot_token:
            raise ValueError("⚠️  TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        if not self.channel_id:
            raise ValueError("⚠️  TELEGRAM_CHANNEL_ID не найден в переменных окружения")
    
    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Отправляет текстовое сообщение в канал"""
        try:
            url = f"{self.api_url}/sendMessage"
            data = {
                'chat_id': self.channel_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': False
            }
            
            print(f"📤 Отправляем в канал: {self.channel_id}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as response:
                    result = await response.json()
                    
                    if result.get('ok'):
                        print("✅ Сообщение успешно отправлено")
                        return True
                    else:
                        print(f"❌ Ошибка отправки: {result.get('description', 'Неизвестная ошибка')}")
                        print(f"❌ Полный ответ API: {result}")
                        return False
                        
        except Exception as e:
            print(f"❌ Ошибка при отправке сообщения: {e}")
            return False
    
    async def send_photo(self, photo_path: str, caption: str = "", parse_mode: str = "HTML") -> bool:
        """Отправляет фото с подписью в канал"""
        try:
            url = f"{self.api_url}/sendPhoto"
            
            # Проверяем, существует ли файл
            if not os.path.exists(photo_path):
                print(f"❌ Файл не найден: {photo_path}")
                return False
            
            data = {
                'chat_id': self.channel_id,
                'caption': caption,
                'parse_mode': parse_mode
            }
            
            async with aiohttp.ClientSession() as session:
                with open(photo_path, 'rb') as photo_file:
                    files = {'photo': photo_file}
                    
                    async with session.post(url, data=data, files=files) as response:
                        result = await response.json()
                        
                        if result.get('ok'):
                            print(f"✅ Фото отправлено: {photo_path}")
                            return True
                        else:
                            print(f"❌ Ошибка отправки фото: {result.get('description', 'Неизвестная ошибка')}")
                            return False
                            
        except Exception as e:
            print(f"❌ Ошибка при отправке фото: {e}")
            return False
    
    async def send_photo_from_url(self, photo_url: str, caption: str = "", parse_mode: str = "HTML") -> bool:
        """Отправляет фото по URL с подписью в канал"""
        try:
            url = f"{self.api_url}/sendPhoto"
            data = {
                'chat_id': self.channel_id,
                'photo': photo_url,
                'caption': caption,
                'parse_mode': parse_mode
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as response:
                    result = await response.json()
                    
                    if result.get('ok'):
                        print(f"✅ Фото по URL отправлено: {photo_url}")
                        return True
                    else:
                        print(f"❌ Ошибка отправки фото по URL: {result.get('description', 'Неизвестная ошибка')}")
                        return False
                        
        except Exception as e:
            print(f"❌ Ошибка при отправке фото по URL: {e}")
            return False
    
    def format_news_for_telegram(self, article: Dict[str, Any]) -> str:
        """Форматирует новость для Telegram с HTML разметкой"""
        title = article.get('title', '')
        summary = article.get('summary', '') or article.get('post_text', '')
        
        # Очищаем summary от лишних символов и хештегов для красивого форматирования
        if summary.startswith('⚽'):
            summary = summary[2:].strip()
        
        # Убираем хештеги из summary для отдельного размещения
        summary_clean = summary
        if '#футбол' in summary:
            summary_clean = summary.split('#футбол')[0].strip()
        
        # Формируем сообщение с HTML разметкой
        message = f"<b>⚽ {title}</b>\n\n"
        
        if summary_clean and summary_clean != title:
            message += f"{summary_clean}\n\n"
        
        # Добавляем хештеги
        message += "🏷 #футбол #новини #спорт #football"
        
        return message
    
    async def post_article(self, article: Dict[str, Any]) -> bool:
        """Публикует одну статью в канал"""
        try:
            print(f"📤 Публикуем: {article.get('title', '')[:50]}...")
            
            # Форматируем текст
            message_text = self.format_news_for_telegram(article)
            
            # Проверяем наличие изображения
            image_path = article.get('image_path', '')
            image_url = article.get('image_url', '')
            
            success = False
            
            # Пытаемся отправить с фото (локальный файл)
            if image_path and os.path.exists(image_path):
                success = await self.send_photo(image_path, message_text)
            
            # Если локального файла нет, пытаемся отправить по URL
            elif image_url:
                success = await self.send_photo_from_url(image_url, message_text)
            
            # Если фото нет или не удалось отправить, отправляем только текст
            if not success:
                print("📝 Отправляем только текст (без фото)")
                success = await self.send_message(message_text)
            
            if success:
                print(f"✅ Статья опубликована успешно")
                return True
            else:
                print(f"❌ Не удалось опубликовать статью")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка публикации статьи: {e}")
            return False
    
    async def post_multiple_articles(self, articles: List[Dict[str, Any]], delay: int = 5) -> int:
        """Публикует несколько статей с задержкой между постами"""
        successful_posts = 0
        
        print(f"📢 Начинаем публикацию {len(articles)} статей в канал")
        print(f"⏱️  Задержка между постами: {delay} секунд")
        print("=" * 60)
        
        for i, article in enumerate(articles, 1):
            print(f"\n📤 Пост {i}/{len(articles)}")
            
            success = await self.post_article(article)
            
            if success:
                successful_posts += 1
            
            # Задержка между постами (кроме последнего)
            if i < len(articles):
                print(f"⏳ Ждем {delay} секунд перед следующим постом...")
                await asyncio.sleep(delay)
        
        print(f"\n📊 Публикация завершена!")
        print(f"✅ Успешно опубликовано: {successful_posts}/{len(articles)}")
        print(f"❌ Не удалось опубликовать: {len(articles) - successful_posts}")
        
        return successful_posts
    
    async def test_connection(self) -> bool:
        """Тестирует подключение к Telegram API"""
        try:
            url = f"{self.api_url}/getMe"
            print(f"🔗 Тестируем подключение к: {url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    result = await response.json()
                    
                    if result.get('ok'):
                        bot_info = result.get('result', {})
                        print(f"✅ Подключение к Telegram успешно!")
                        print(f"🤖 Бот: @{bot_info.get('username', 'unknown')}")
                        print(f"📋 Имя: {bot_info.get('first_name', 'unknown')}")
                        return True
                    else:
                        print(f"❌ Ошибка подключения: {result.get('description', 'Неизвестная ошибка')}")
                        print(f"❌ Полный ответ API: {result}")
                        return False
                        
        except Exception as e:
            print(f"❌ Ошибка тестирования подключения: {e}")
            return False

# Синхронная обертка для использования в основном коде
class TelegramPosterSync:
    def __init__(self, bot_token: str = None, channel_id: str = None):
        self.poster = TelegramPoster(bot_token, channel_id)
    
    def post_articles(self, articles: List[Dict[str, Any]], delay: int = 5) -> int:
        """Синхронная функция для публикации статей"""
        return asyncio.run(self.poster.post_multiple_articles(articles, delay))
    
    def test_connection(self) -> bool:
        """Синхронная функция для тестирования подключения"""
        return asyncio.run(self.poster.test_connection())
    
    def post_single_article(self, article: Dict[str, Any]) -> bool:
        """Синхронная функция для публикации одной статьи"""
        return asyncio.run(self.poster.post_article(article))

def test_telegram_poster():
    """Тестирование Telegram постера"""
    print("🧪 ТЕСТИРОВАНИЕ TELEGRAM ПОСТЕРА")
    print("=" * 50)
    
    try:
        poster = TelegramPosterSync()
        
        # Тестируем подключение
        if poster.test_connection():
            print("\n🧪 Отправляем тестовое сообщение...")
            
            test_article = {
                'title': 'Тестова новина',
                'summary': 'Це тестове повідомлення для перевірки роботи бота',
                'image_path': '',
                'image_url': '',
                'url': 'https://football.ua/'
            }
            
            success = poster.post_single_article(test_article)
            
            if success:
                print("✅ Тест успешен! Бот готов к работе")
            else:
                print("❌ Тест не прошел")
        
    except ValueError as e:
        print(f"❌ Ошибка конфигурации: {e}")
        print("\n🔧 ИНСТРУКЦИЯ ПО НАСТРОЙКЕ RAILWAY:")
        print("1. Зайдите в ваш проект на Railway")
        print("2. Перейдите в раздел 'Variables'")
        print("3. Добавьте переменные:")
        print("   TELEGRAM_BOT_TOKEN = ваш_bot_token")
        print("   TELEGRAM_CHANNEL_ID = @ваш_канал или -1001234567890")
        print("4. Перезапустите деплой")
        
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")

if __name__ == "__main__":
    test_telegram_poster()
