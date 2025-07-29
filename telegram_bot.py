import os
import requests
import time
from typing import List, Dict, Any

def debug_environment():
    """Отладка переменных окружения"""
    print("🔍 ПОЛНАЯ ОТЛАДКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ:")
    print("=" * 60)
    
    # Общая информация
    print(f"Всего переменных окружения: {len(os.environ)}")
    
    # Telegram переменные
    telegram_vars = {k: v for k, v in os.environ.items() if 'TELEGRAM' in k.upper()}
    print(f"\n📋 Telegram переменные ({len(telegram_vars)}):")
    if telegram_vars:
        for key, value in telegram_vars.items():
            masked_value = value[:15] + "..." if len(value) > 15 else value
            print(f"   ✅ {key} = {masked_value}")
    else:
        print("   ❌ НЕТ переменных с TELEGRAM")
    
    # Проверяем конкретные переменные
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
    
    print(f"\n🔑 TELEGRAM_BOT_TOKEN: {'✅ НАЙДЕН' if bot_token else '❌ НЕ НАЙДЕН'}")
    print(f"📢 TELEGRAM_CHANNEL_ID: {'✅ НАЙДЕН (' + channel_id + ')' if channel_id else '❌ НЕ НАЙДЕН'}")
    
    # Показываем примеры других переменных (для диагностики Railway)
    print(f"\n🔍 Примеры других переменных окружения:")
    other_vars = [k for k in os.environ.keys() if 'TELEGRAM' not in k.upper()][:5]
    for key in other_vars:
        value = os.environ[key]
        masked_value = value[:20] + "..." if len(value) > 20 else value
        print(f"   {key} = {masked_value}")
    
    print("=" * 60)
    
    return bool(bot_token and channel_id)

def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """Отправляет сообщение в Telegram канал"""
    
    # Отладка среды
    env_ok = debug_environment()
    
    if not env_ok:
        print("❌ Переменные окружения не настроены")
        return False
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            'chat_id': channel_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': False
        }
        
        print(f"📤 Отправляем сообщение в канал: {channel_id}")
        
        response = requests.post(url, data=data, timeout=10)
        result = response.json()
        
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

def send_photo(photo_path: str, caption: str = "", parse_mode: str = "HTML") -> bool:
    """Отправляет фото с подписью"""
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
    
    if not bot_token or not channel_id:
        print("❌ Настройки Telegram не найдены")
        return False
    
    if not os.path.exists(photo_path):
        print(f"❌ Файл не найден: {photo_path}")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        
        with open(photo_path, 'rb') as photo_file:
            files = {'photo': photo_file}
            data = {
                'chat_id': channel_id,
                'caption': caption,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, data=data, files=files, timeout=30)
            result = response.json()
            
            if result.get('ok'):
                print(f"✅ Фото отправлено: {photo_path}")
                return True
            else:
                print(f"❌ Ошибка отправки фото: {result.get('description', 'Неизвестная ошибка')}")
                return False
                
    except Exception as e:
        print(f"❌ Ошибка при отправке фото: {e}")
        return False

def send_photo_url(photo_url: str, caption: str = "", parse_mode: str = "HTML") -> bool:
    """Отправляет фото по URL"""
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
    
    if not bot_token or not channel_id:
        print("❌ Настройки Telegram не найдены")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        data = {
            'chat_id': channel_id,
            'photo': photo_url,
            'caption': caption,
            'parse_mode': parse_mode
        }
        
        response = requests.post(url, data=data, timeout=30)
        result = response.json()
        
        if result.get('ok'):
            print(f"✅ Фото по URL отправлено: {photo_url}")
            return True
        else:
            print(f"❌ Ошибка отправки фото по URL: {result.get('description', 'Неизвестная ошибка')}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при отправке фото по URL: {e}")
        return False

def post_article(article: Dict[str, Any]) -> bool:
    """Публикует одну статью"""
    try:
        print(f"📤 Публикуем: {article.get('title', '')[:50]}...")
        
        # Используем готовый текст или создаем базовый
        message_text = article.get('post_text', '')
        if not message_text:
            title = article.get('title', '')
            summary = article.get('summary', '')
            message_text = f"<b>⚽ {title}</b>\n\n"
            if summary and summary != title:
                message_text += f"{summary}\n\n"
            message_text += "🏷 #футбол #новини #спорт #football"
        
        # Проверяем наличие изображения
        image_path = article.get('image_path', '')
        image_url = article.get('image_url', '')
        
        success = False
        
        # Пытаемся отправить с фото (локальный файл)
        if image_path and os.path.exists(image_path):
            success = send_photo(image_path, message_text)
        
        # Если локального файла нет, пытаемся отправить по URL
        elif image_url:
            success = send_photo_url(image_url, message_text)
        
        # Если фото нет или не удалось отправить, отправляем только текст
        if not success:
            print("📝 Отправляем только текст (без фото)")
            success = send_message(message_text)
        
        return success
        
    except Exception as e:
        print(f"❌ Ошибка публикации статьи: {e}")
        return False

def post_articles(articles: List[Dict[str, Any]], delay: int = 3) -> int:
    """Публикует несколько статей с задержкой"""
    successful_posts = 0
    
    print(f"📢 Начинаем публикацию {len(articles)} статей")
    print(f"⏱️  Задержка между постами: {delay} секунд")
    print("=" * 60)
    
    for i, article in enumerate(articles, 1):
        print(f"\n📤 Пост {i}/{len(articles)}")
        
        success = post_article(article)
        
        if success:
            successful_posts += 1
        
        # Задержка между постами (кроме последнего)
        if i < len(articles):
            print(f"⏳ Ждем {delay} секунд перед следующим постом...")
            time.sleep(delay)
    
    print(f"\n📊 Публикация завершена!")
    print(f"✅ Успешно опубликовано: {successful_posts}/{len(articles)}")
    print(f"❌ Не удалось опубликовать: {len(articles) - successful_posts}")
    
    return successful_posts

def test_connection() -> bool:
    """Тестирует подключение к Telegram API"""
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN не найден")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getMe"
        response = requests.get(url, timeout=10)
        result = response.json()
        
        if result.get('ok'):
            bot_info = result.get('result', {})
            print(f"✅ Подключение к Telegram успешно!")
            print(f"🤖 Бот: @{bot_info.get('username', 'unknown')}")
            print(f"📋 Имя: {bot_info.get('first_name', 'unknown')}")
            return True
        else:
            print(f"❌ Ошибка подключения: {result.get('description', 'Неизвестная ошибка')}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования подключения: {e}")
        return False

# Класс для совместимости с telegram_poster
class TelegramPosterSync:
    def __init__(self):
        pass
    
    def test_connection(self) -> bool:
        return test_connection()
    
    def post_articles(self, articles: List[Dict[str, Any]], delay: int = 3) -> int:
        return post_articles(articles, delay)
    
    def post_single_article(self, article: Dict[str, Any]) -> bool:
        return post_article(article)
    
    # Добавляем недостающий метод post_article
    def post_article(self, article: Dict[str, Any]) -> bool:
        """Публикует одну статью - алиас для post_single_article"""
        return self.post_single_article(article)

if __name__ == "__main__":
    print("🧪 ТЕСТИРОВАНИЕ TELEGRAM БОТА")
    print("=" * 50)
    
    # Проверяем среду
    env_ok = debug_environment()
    
    if env_ok:
        # Тестируем подключение
        if test_connection():
            print("\n🧪 Отправляем тестовое сообщение...")
            
            test_message = """<b>⚽ Тестова новина</b>

Це тестове повідомлення для перевірки роботи бота

🏷 #футбол #новини #спорт #football"""
            
            success = send_message(test_message)
            
            if success:
                print("✅ Тест успешен! Бот готов к работе")
            else:
                print("❌ Тест не прошел")
        else:
            print("❌ Не удалось подключиться к Telegram API")
    else:
        print("❌ Переменные окружения не настроены")
        print("\n🛠️  НАСТРОЙКА НА RAILWAY:")
        print("1. Зайдите в проект на Railway")
        print("2. Variables → Add Variable")
        print("3. Добавьте TELEGRAM_BOT_TOKEN")
        print("4. Добавьте TELEGRAM_CHANNEL_ID")
        print("5. Redeploy проект")
