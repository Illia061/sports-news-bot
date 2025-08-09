import os
import requests
from typing import Dict, Any
from urllib.parse import urlparse
import google.generativeai as genai
import time
from bs4 import BeautifulSoup
import logging
import random

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурационные параметры
CONFIG = {
    'CONTENT_MAX_LENGTH': 2000,
    'SUMMARY_MAX_WORDS': 150,
    'USER_AGENTS': [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0'
    ]
}

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_AVAILABLE = False
model = None

def init_gemini():
    """Инициализирует клиента Gemini."""
    global GEMINI_AVAILABLE, model
    if GEMINI_AVAILABLE:  # Кэшируем результат
        return
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY не найден - AI функции отключены")
        return
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        GEMINI_AVAILABLE = True
        logger.info("Gemini инициализирован")
    except Exception as e:
        logger.error(f"Ошибка инициализации Gemini: {e}")

def has_gemini_key() -> bool:
    """Проверяет наличие ключа Gemini и инициализирует, если нужно."""
    if not GEMINI_AVAILABLE:
        init_gemini()
    return GEMINI_AVAILABLE

def fetch_full_article_content(url: str) -> str:
    """Загружает полный текст статьи по URL."""
    try:
        headers = {'User-Agent': random.choice(CONFIG['USER_AGENTS'])}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        content_selectors = (
            [
                '.RichTextStoryBody', '.Story__Body', '.ArticleBody',
                '[data-module="ArticleBody"]', '.story-body', '.article-body'
            ] if 'espn.com' in url else
            [
                # OneFootball специфические селекторы
                '[data-testid="article-body"]', '.ArticleBody',
                # Общие селекторы
                '.article-content', '.post-content', '.entry-content',
                '[class*="content"]', '.article-body', '.post-body'
            ] if 'onefootball.com' in url else
            [
                '.article-content', '.post-content', '.entry-content',
                '[class*="content"]', '.article-body', '.post-body'
            ]
        )

        article_text = ""
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                for unwanted in content_div.find_all(['script', 'style', 'iframe', 'ads', 'aside']):
                    unwanted.decompose()
                article_text = content_div.get_text(strip=True)
                break

        if not article_text:
            paragraphs = soup.find_all('p')
            article_text = ' '.join(p.get_text(strip=True) for p in paragraphs)

        article_text = ' '.join(article_text.split())
        return article_text[:CONFIG['CONTENT_MAX_LENGTH']]

    except Exception as e:
        logger.error(f"Ошибка загрузки статьи {url}: {e}")
        return ""

def create_basic_summary(article_data: Dict[str, Any]) -> str:
    """Создает базовое резюме без использования AI."""
    content = article_data.get('content', '')
    summary = article_data.get('summary', '')
    title = article_data.get('title', '')

    if content and len(content) > 50:
        sentences = content.split('. ')
        meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 20][:2]
        if meaningful_sentences:
            result = '. '.join(meaningful_sentences)
            return result + '.' if not result.endswith('.') else result
    return summary or title

def create_enhanced_summary(article_data: Dict[str, Any]) -> str:
    """Создает резюме с использованием Gemini или базовое резюме."""
    title = article_data.get('title', '')
    content = article_data.get('content', '')
    summary = article_data.get('summary', '')
    url = article_data.get('url', '')
    source = article_data.get('source', '')
    
    # Проверяем наличие уже обработанного контента (для OneFootball)
    processed_content = article_data.get('processed_content', '')
    is_onefootball = source == 'OneFootball'
    is_espn_translated = source == 'ESPN Soccer' and article_data.get('original_content')

    if not has_gemini_key() or not model:
        return create_basic_summary(article_data)

    # Для OneFootball используем оригинальный контент, если нет processed_content
    if is_onefootball and not processed_content:
        logger.info(f"OneFootball: используем оригинальный контент для AI обработки")
        # Если контент короткий и нет полного текста, загружаем
        if len(content) < 100 and url:
            logger.info(f"OneFootball: контент короткий ({len(content)} символов), загружаем полный текст...")
            content = fetch_full_article_content(url) or summary or title
            logger.info(f"OneFootball: загружено {len(content)} символов контента")
    elif is_onefootball and processed_content:
        # Используем уже обработанный контент
        logger.info(f"OneFootball: используем обработанный контент ({len(processed_content)} символов)")
        return processed_content

    # Для других источников
    if not is_onefootball and len(content) < 100 and url:
        logger.info(f"Контент короткий ({len(content)} символов), загружаем полный текст...")
        content = fetch_full_article_content(url) or summary or title
        logger.info(f"Загружено {len(content)} символов контента")

    if len(content) < 20:
        logger.warning("Недостаточно контента для обработки")
        return summary or title

    logger.info(f"Отправляем в Gemini {len(content)} символов")
    
    # Определяем тип промпта
    if is_onefootball:
        prompt = f"""Ти редактор футбольних новин. Переклади англійський текст українською та створи КОРОТКИЙ пост для Telegram (макс. {CONFIG['SUMMARY_MAX_WORDS']} слів).

Правила:
- Переклади точно та природно українською мовою
- Тільки ключові факти, без прикрас
- Максимум 1-2 речення прямої мови
- Структура: головний факт (1-2 речення), деталі (2-4 речення)
- Для трансферів: вказуй суму, термін контракту
- Для матчів: результат, ключові моменти

Заголовок (англ.): {title}
Текст (англ.): {content}

КОРОТКИЙ ПОСТ УКРАЇНСЬКОЮ:"""
    elif is_espn_translated:
        prompt = f"""Ти редактор футбольних новин. Створи КОРОТКИЙ пост для Telegram (макс. {CONFIG['SUMMARY_MAX_WORDS']} слів) з перекладеного контенту ESPN.

Правила:
- Тільки ключові факти
- Контент уже українською
- Максимум 1-2 речення прямої мови
- Для рейтингів: лише топ-5
- Структура: головний факт (1-2 речення), деталі (2-4 речення)

Заголовок: {title}
Текст: {content}

КОРОТКИЙ ПОСТ:"""
    else:
        prompt = f"""Ти редактор футбольних новин. Створи КОРОТКИЙ пост для Telegram (макс. {CONFIG['SUMMARY_MAX_WORDS']} слів).

Правила:
- Тільки ключові факти, без прикрас
- Українською мовою
- Максимум 1-2 речення прямої мови
- Не повторюй заголовок
- Для рейтингів: лише топ-5
- Структура: головний факт (1-2 речення), деталі (2-4 речення)

Заголовок: {title}
Текст: {content}

КОРОТКИЙ ПОСТ:"""

    try:
        response = model.generate_content(prompt)
        summary_result = response.text.strip()
        if summary_result.lower() == title.lower():
            logger.warning("AI вернул только заголовок, используем обрезанный контент")
            return content[:200] + '...' if len(content) > 200 else content
        logger.info(f"AI обработал контент: {len(summary_result)} символов")
        return summary_result
    except Exception as e:
        logger.error(f"Ошибка Gemini: {e}")
        time.sleep(1)
        return content[:200] + '...' if len(content) > 200 else content

def format_for_social_media(article_data: Dict[str, Any]) -> str:
    """Форматирует статью для соцсетей."""
    title = article_data.get('title', '')
    content = article_data.get('content', '')
    summary = article_data.get('summary', '')
    url = article_data.get('url', '') or article_data.get('link', '')
    source = article_data.get('source', '')

    logger.info(f"Форматируем для соцсетей [{source}]: {title[:50]}...")
    
    # Создаем расширенное резюме
    ai_summary = create_enhanced_summary({
        'title': title, 
        'content': content, 
        'summary': summary,
        'url': url, 
        'source': source, 
        'original_content': article_data.get('original_content', ''),
        'processed_content': article_data.get('processed_content', '')
    })

    # Убираем нежелательные префиксы
    unwanted_prefixes = ["Інше", "Італія", "Іспанія", "Німеччина", "Чемпіонат", "Сьогодні", "Вчера"]
    for prefix in unwanted_prefixes:
        if ai_summary.startswith(prefix):
            ai_summary = ai_summary[len(prefix):].strip(": ").lstrip()

    # Форматируем пост в зависимости от источника
    if source == 'OneFootball':
        post = f"<b>🌍 {title}</b>\n\n{ai_summary}\n\n📰 OneFootball\n#футбол #новини #світ"
    elif source == 'ESPN Soccer':
        post = f"<b>🌍 {title}</b>\n\n{ai_summary}\n\n📰 ESPN Soccer\n#футбол #новини #ESPN #світ"
    else:
        post = f"<b>⚽ {title}</b>\n\n{ai_summary}\n\n#футбол #новини #спорт"
    
    logger.info(f"Готовый пост [{source}]: {len(post)} символов")
    return post

def download_image(image_url: str, filename: str = None) -> str:
    """Загружает изображение по URL."""
    if not image_url:
        return ""
    try:
        images_dir = "images"
        os.makedirs(images_dir, exist_ok=True)
        if not filename:
            parsed_url = urlparse(image_url)
            filename = os.path.basename(parsed_url.path) or f"image_{hash(image_url) % 10000}.jpg"
        filepath = os.path.join(images_dir, filename)

        headers = {
            "User-Agent": random.choice(CONFIG['USER_AGENTS']),
            **({"Referer": "https://www.espn.com/", "Accept": "image/webp,image/apng,image/*,*/*;q=0.8"}
               if 'espn.com' in image_url else 
               {"Referer": "https://onefootball.com/", "Accept": "image/webp,image/apng,image/*,*/*;q=0.8"}
               if 'onefootball.com' in image_url else {})
        }
        response = requests.get(image_url, headers=headers, timeout=10)
        response.raise_for_status()
        with open(filepath, 'wb') as f:
            f.write(response.content)
        logger.info(f"🖼️ Изображение загружено: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Ошибка загрузки изображения {image_url}: {e}")
        return ""

def process_article_for_posting(article_data: Dict[str, Any]) -> Dict[str, Any]:
    """Обрабатывает статью для публикации."""
    source = article_data.get('source', 'Unknown')
    logger.info(f"Обрабатываем статью [{source}]: {article_data.get('title', '')[:50]}...")
    
    post_text = format_for_social_media(article_data)
    image_path = download_image(article_data.get('image_url', ''))

    result = {
        'title': article_data.get('title', ''),
        'post_text': post_text,
        'image_path': image_path,
        'image_url': article_data.get('image_url', ''),
        'url': article_data.get('url', '') or article_data.get('link', ''),
        'summary': article_data.get('summary', ''),
        'source': source,
        **(
            {
                'original_title': article_data.get('original_title', ''),
                'original_content': article_data.get('original_content', ''),
                'processed_content': article_data.get('processed_content', '')
            }
            if source in ['ESPN Soccer', 'OneFootball'] else {}
        )
    }
    logger.info(f"Статья [{source}] обработана успешно")
    return result

# Совместимость со старым интерфейсом
def summarize_news(title: str, url: str, content: str = '') -> str:
    return create_enhanced_summary({'title': title, 'url': url, 'content': content, 'summary': title})

def simple_summarize(title: str, url: str) -> str:
    return f"🔸 {title}"
