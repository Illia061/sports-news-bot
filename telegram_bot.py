
import os
import requests

def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """Отправляет сообщение в Telegram канал"""
    
    # Получаем переменные окружения
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
    
    # Отладочная информация
    print("🔍 ОТЛАДКА TELEGRAM:")
    print(f"Bot token: {'Есть' if bot_token else 'НЕТ!'}")
    print(f"Channel ID: {channel_id if channel_id else 'НЕТ!'}")
    
    # Показываем все переменные с TELEGRAM
    telegram_vars = {k: v for k, v in os.environ.items() if 'TELEGRAM' in k.upper()}
    print(f"Найдено переменных с TELEGRAM: {len(telegram_vars)}")
    for key, value in telegram_vars.items():
        masked_value = value[:10] + "..." if len(value) > 10 else value
        print(f"  {key} = {masked_value}")
    
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        return False
        
    if not channel_id:
        print("❌ TELEGRAM_CHANNEL_ID не найден в переменных окружения")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            'chat_id': channel_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': False
        }
        
        print(f"📤 Отправляем сообщение в канал: {channel_id}")
        
        response = requests.post(url, data=data)
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
