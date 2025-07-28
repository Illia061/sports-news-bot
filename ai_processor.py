
import os
from typing import Dict, Any

# Безопасная инициализация OpenAI клиента
client = None

def init_openai_client():
    """Инициализирует OpenAI клиента"""
    global client
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  OPENAI_API_KEY не найден - AI отключен")
        return
    client = OpenAI(api_key=api_key)
    print("✅ OpenAI клиент инициализирован")

def create_enhanced_summary(article_data: Dict[str, Any]) -> str:
    """Создает улучшенное резюме новости"""
    if not client:
        init_openai_client()
    if not client:
        return article_data.get('summary', '') or article_data.get('title', '')

    try:
        title = article_data.get('title', '')
        content = article_data.get('content', '') or article_data.get('summary', '') or title

        prompt = f""" Ти редактор футбольних новин
Перефразуй і створи інформативний виклад цієї футбольної новини українською мовою.

Вимоги:
- Зрозуміло та цікаво
- Збережи всі важливі факти
- Українською мовою
- Без зайвих деталей
- Якщо у статті є рейтинг - публікуєш його повністю
- Якщо у статті є пряма мова - публікуєш стислу вижимку на 3-4 речення

Заголовок: {title}
Текст: {content[:1000]}

Стислий виклад:
"""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "Ти - експерт зі створення стислих викладів футбольних новин українською мовою. Твоя мета - зробити новину цікавою та зрозумілою."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            max_tokens=400,
            temperature=0.7
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"❌ Ошибка AI: {e}")
        return article_data.get('summary', '') or article_data.get('title', '')

def format_for_social_media(article_data: Dict[str, Any]) -> str:
    """Форматирует новость для Telegram"""
    title = article_data.get('title', '')
    summary = article_data.get('summary', '')
    content = article_data.get('content', '')

    text = content or summary or title
    ai_summary = create_enhanced_summary({"title": title, "content": text})

    post = f"<b>{title}</b>\n\n{ai_summary}\n\n#футбол #новини"
    return post

def process_article_for_posting(article_data: Dict[str, Any]) -> Dict[str, Any]:
    """Готовит данные для публикации"""
    post_text = format_for_social_media(article_data)
    image_path = ""
    return {
        'title': article_data.get('title', ''),
        'post_text': post_text,
        'image_path': image_path,
        'image_url': article_data.get('image_url', ''),
        'url': article_data.get('url', ''),
        'summary': article_data.get('summary', '')
    }
