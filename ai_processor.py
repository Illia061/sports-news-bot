import os
import requests
from typing import Dict, Any
from urllib.parse import urlparse
import google.generativeai as genai
import time
from bs4 import BeautifulSoup

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

def fetch_full_article_content(url: str) -> str:
    """Загружает полный текст статьи по URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Ищем основной контент статьи (адаптируйте селекторы под структуру football.ua)
        content_selectors = [
            '.article-content',
            '.post-content', 
            '.entry-content',
            '[class*="content"]',
            '.article-body',
            '.post-body'
        ]
        
        article_text = ""
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                # Удаляем ненужные элементы
                for unwanted in content_div.find_all(['script', 'style', 'iframe', 'ads']):
                    unwanted.decompose()
                
                article_text = content_div.get_text(strip=True)
                break
        
        # Если не нашли специальный контейнер, берем все параграфы
        if not article_text:
            paragraphs = soup.find_all('p')
            article_text = ' '.join([p.get_text(strip=True) for p in paragraphs])
        
        # Очищаем текст
        article_text = ' '.join(article_text.split())  # Убираем лишние пробелы
        
        return article_text[:2000]  # Ограничиваем длину для AI
        
    except Exception as e:
        print(f"❌ Ошибка загрузки полного текста статьи: {e}")
        return ""

def create_enhanced_summary(article_data: Dict[str, Any]) -> str:
    """Создание резюме через Gemini"""
    if not has_gemini_key() or not model:
        return article_data.get('summary', '') or article_data.get('title', '')

    title = article_data.get('title', '')
    content = article_data.get('content', '')
    
    # Парсер уже загрузил полный контент, используем его
    if content:
        print(f"🤖 Обрабатываем {len(content)} символов контента через AI")
    else:
        # Если контента нет, используем summary
        content = article_data.get('summary', '') or title
        print(f"⚠️ Контент не найден, используем summary: {len(content)} символов")

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
            'content': content,
            'summary': summary,
            'url': article_data.get('url', '') or article_data.get('link', '')  # Передаем URL для загрузки
        })
    else:
        ai_summary = summary or content[:200] + '...' if len(content) > 200 else content

    # Remove unwanted prefixes
    unwanted_prefixes = ["Інше", "Італія", "Іспанія", "Німеччина", "Чемпіонат", "Сьогодні", "Вчера"]
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
        'url': article_data.get('url', '') or article_data.get('link', ''),
        'summary': article_data.get('summary', '')
    }

# Old compatible interfaces
def summarize_news(title: str, url: str, content: str = '') -> str:
    article_data = {'title': title, 'url': url, 'content': content, 'summary': title}
    return create_enhanced_summary(article_data) if has_gemini_key() else f"🔸 {title}"

def simple_summarize(title: str, url: str) -> str:
    return f"🔸 {title}"

