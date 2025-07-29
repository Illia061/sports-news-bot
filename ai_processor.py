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
        model = genai.GenerativeModel("gemini-2.5-flash")
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
        # Если нет AI, создаем простое резюме из контента
        content = article_data.get('content', '')
        summary = article_data.get('summary', '')
        title = article_data.get('title', '')
        
        if content and len(content) > 50:
            # Берем первые 2-3 предложения из контента
            sentences = content.split('. ')
            meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
            if meaningful_sentences:
                result = '. '.join(meaningful_sentences[:2])
                if not result.endswith('.'):
                    result += '.'
                return result
        
        return summary or title

    title = article_data.get('title', '')
    content = article_data.get('content', '')
    summary = article_data.get('summary', '')
    url = article_data.get('url', '')
    
    # ГЛАВНАЯ ПРОБЛЕМА БЫЛА ЗДЕСЬ: если content пустой, пытаемся загрузить его
    if not content or len(content) < 100:
        print(f"🔄 Контент короткий ({len(content)} символов), загружаем полный текст...")
        if url:
            full_content = fetch_full_article_content(url)
            if full_content:
                content = full_content
                print(f"✅ Загружен полный контент: {len(content)} символов")
            else:
                print("⚠️ Не удалось загрузить полный контент, используем summary")
                content = summary or title
    
    # Проверяем, что у нас есть достаточно контента для обработки
    if not content or len(content) < 20:
        print("⚠️ Недостаточно контента для AI обработки")
        return summary or title

    print(f"🤖 Отправляем в Gemini {len(content)} символов контента")

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
        summary_result = response.text.strip()
        
        # Ensure summary isn't just the title
        if summary_result.lower() == title.lower():
            print("⚠️ AI вернул только заголовок, используем обрезанный контент")
            return content[:200] + '...' if len(content) > 200 else content
        
        print(f"✅ AI обработал контент: {len(summary_result)} символов")
        return summary_result
        
    except Exception as e:
        print(f"❌ Ошибка Gemini: {e}")
        time.sleep(1)  # Small delay to prevent rate limiting
        # Возвращаем обрезанный контент как fallback
        return content[:200] + '...' if len(content) > 200 else content

def format_for_social_media(article_data: Dict[str, Any]) -> str:
    title = article_data.get('title', '')
    content = article_data.get('content', '')
    summary = article_data.get('summary', '')
    url = article_data.get('url', '') or article_data.get('link', '')

    print(f"📝 Форматируем для соцсетей: {title[:50]}...")
    print(f"   Контент: {len(content)} символов")
    print(f"   Summary: {len(summary)} символов")

    if has_gemini_key():
        print("🤖 Используем AI для создания резюме...")
        ai_summary = create_enhanced_summary({
            'title': title,
            'content': content,
            'summary': summary,
            'url': url
        })
    else:
        print("📝 Используем базовое резюме...")
        # Улучшенная обработка без AI
        if content and len(content) > 50:
            # Берем первые предложения из контента
            sentences = content.split('. ')
            meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
            if meaningful_sentences:
                ai_summary = '. '.join(meaningful_sentences[:2])
                if not ai_summary.endswith('.'):
                    ai_summary += '.'
            else:
                ai_summary = content[:200] + '...' if len(content) > 200 else content
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
    
    print(f"✅ Готовый пост: {len(post)} символов")
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
    print(f"🔄 Обрабатываем статью: {article_data.get('title', '')[:50]}...")
    
    post_text = format_for_social_media(article_data)
    image_path = download_image(article_data['image_url']) if article_data.get('image_url') else ""
    
    result = {
        'title': article_data.get('title', ''),
        'post_text': post_text,
        'image_path': image_path,
        'image_url': article_data.get('image_url', ''),
        'url': article_data.get('url', '') or article_data.get('link', ''),
        'summary': article_data.get('summary', '')
    }
    
    print(f"✅ Статья обработана успешно")
    return result

# Old compatible interfaces
def summarize_news(title: str, url: str, content: str = '') -> str:
    article_data = {'title': title, 'url': url, 'content': content, 'summary': title}
    return create_enhanced_summary(article_data) if has_gemini_key() else f"🔸 {title}"

def simple_summarize(title: str, url: str) -> str:
    return f"🔸 {title}"
