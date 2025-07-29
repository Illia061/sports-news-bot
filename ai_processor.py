import os
import requests
from typing import Dict, Any
from urllib.parse import urlparse
import google.generativeai as genai
import time

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_AVAILABLE = False
model = None

def init_gemini():
    """Инициализирует клиента Gemini"""
    global GEMINI_AVAILABLE, model
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY не найден - AI функции отключены")
        return
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("models/gemini-pro")
        GEMINI_AVAILABLE = True
        print("✅ Gemini инициализирован")
    except Exception as e:
        print(f"❌ Ошибка инициализации Gemini: {e}")

def has_gemini_key() -> bool:
    if not GEMINI_AVAILABLE:
        init_gemini()
    return GEMINI_AVAILABLE

def create_enhanced_summary(article_data: Dict[str, Any]) -> str:
    """Создание резюме через Gemini"""
    if not has_gemini_key() or not model:
        return article_data.get('summary', '') or article_data.get('title', '')

    title = article_data.get('title', '')
    content = article_data.get('content', '') or article_data.get('summary', '') or title

    prompt = f"""Ти редактор футбольних новин.
Перефразуй і створи інформативний виклад цієї футбольної новини українською мовою.

Вимоги:
- Зрозуміло та цікаво
- Збережи всі важливі факти
- Українською мовою
- Без зайвих деталей
- Якщо є рейтинг — публікуй повністю
- Якщо є пряма мова — виклади її коротко на 3–4 речення
- Максимум 200-250 слів

Заголовок: {title}
Текст: {content}

Стислий виклад:
"""
    try:
        response = model.generate_content(prompt)
        summary = response.text.strip()
        # Ensure summary isn't just the title
        if summary.lower() == title.lower():
            return content[:200] + '...' if len(content) > 200 else content
        return summary
    except Exception as e:
        print(f"❌ Помилка Gemini: {e}")
        time.sleep(1)  # Small delay to prevent rate limiting
        return content[:200] + '...' if len(content) > 200 else content

def format_for_social_media(article_data: Dict[str, Any]) -> str:
    title = article_data.get('title', '')
    content = article_data.get('content', '')
    summary = article_data.get('summary', '')

    if has_gemini_key():
        ai_summary = create_enhanced_summary({
            'title': title,
            'content': content,  # Use full content for AI processing
            'summary': summary
        })
    else:
        ai_summary = summary or content[:200] + '...' if len(content) > 200 else content

    # Remove unwanted prefixes
    unwanted_prefixes = ["Інше", "Італія", "Іспанія", "Німеччина", "Чемпіонат", "Сьогодні", "Вчора"]
    for prefix in unwanted_prefixes:
        if ai_summary.startswith(prefix):
            ai_summary = ai_summary[len(prefix):].strip(": ").lstrip()

    post = f"<b>⚽ {title}</b>\n\n"
    if ai_summary and ai_summary != title:
        post += f"{ai_summary}\n\n"

    post += "#футбол #новини #спорт"
    return post

def download_image(image_url: str, filename: str = None) -> str:
    try:
        if not image_url:
            return ""
        images_dir = "images"
        os.makedirs(images_dir, exist_ok=True)
        if not filename:
            parsed_url = urlparse(image_url)
            filename = os.path.basename(parsed_url.path)
            if not filename or '.' not in filename:
                filename = f"image_{hash(image_url) % 10000}.jpg"
        filepath = os.path.join(images_dir, filename)
        response = requests.get(image_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        with open(filepath, 'wb') as f:
            f.write(response.content)
        return filepath
    except Exception as e:
        print(f"❌ Ошибка загрузки изображения: {e}")
        return ""

def process_article_for_posting(article_data: Dict[str, Any]) -> Dict[str, Any]:
    post_text = format_for_social_media(article_data)
    image_path = download_image(article_data['image_url']) if article_data.get('image_url') else ""
    return {
        'title': article_data.get('title', ''),
        'post_text': post_text,
        'image_path': image_path,
        'image_url': article_data.get('image_url', ''),
        'url': article_data.get('url', ''),
        'summary': article_data.get('summary', '')
    }

# Old compatible interfaces
def summarize_news(title: str, url: str, content: str = '') -> str:
    article_data = {'title': title, 'url': url, 'content': content, 'summary': title}
    return create_enhanced_summary(article_data) if has_gemini_key() else f"🔸 {title}"

def simple_summarize(title: str, url: str) -> str:
    return f"🔸 {title}"

def simple_summarize(title: str, url: str) -> str:
    return f"🔸 {title}"

