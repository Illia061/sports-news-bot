import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import random
from ai_processor import create_enhanced_summary, download_image

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация
CONFIG = {
    'USER_AGENTS': [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0'
    ],
    'BASE_URL': 'https://onefootball.com/en/home',
    'MAX_NEWS': 10
}

KIEV_TZ = ZoneInfo("Europe/Kiev")

def parse_publish_time(time_str: str) -> datetime:
    """Преобразует строку времени в объект datetime с киевским часовым поясом (EEST)."""
    try:
        # Предполагаем формат вроде '2025-08-05T14:30:00Z' или '2025-08-05 14:30 EEST'
        if 'T' in time_str:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00')).astimezone(KIEV_TZ)
        else:
            dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M %Z').astimezone(KIEV_TZ)
        return dt
    except Exception as e:
        logger.warning(f"Ошибка парсинга времени '{time_str}': {e}")
        return datetime.now(KIEV_TZ)

def fetch_full_article(url: str) -> tuple[str, str]:
    """Извлекает полный текст и изображение из статьи."""
    try:
        headers = {'User-Agent': random.choice(CONFIG['USER_AGENTS'])}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Извлечение текста
        content_div = soup.select_one('.article-content, .post-content, [class*="body"]')
        if not content_div:
            paragraphs = soup.find_all('p')
            article_text = ' '.join(p.get_text(strip=True) for p in paragraphs)
        else:
            for unwanted in content_div.find_all(['script', 'style', 'iframe']):
                unwanted.decompose()
            article_text = content_div.get_text(strip=True)

        # Извлечение изображения
        img_elem = soup.select_one('.article-image img, .featured-image img, [class*="image"] img')
        image_url = img_elem['src'] if img_elem and 'src' in img_elem.attrs else ''

        return article_text, image_url
    except Exception as e:
        logger.error(f"Ошибка загрузки статьи {url}: {e}")
        return "", ""

def get_latest_news(since_time: datetime = None) -> list:
    """Получает последние новости с OneFootball с фильтрацией по времени и обработкой статей."""
    logger.info("Получение новостей с OneFootball...")
    news_items = []

    try:
        headers = {'User-Agent': random.choice(CONFIG['USER_AGENTS'])}
        response = requests.get(CONFIG['BASE_URL'], headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        news_container = soup.select('section article')
        if not news_container:
            logger.warning("Контейнер новостей не найден")
            return []

        for article in news_container[:CONFIG['MAX_NEWS']]:
            try:
                title_elem = article.select_one('h3, [class*="title"]')
                title = title_elem.get_text(strip=True) if title_elem else ''

                link_elem = article.select_one('a[href]')
                url = link_elem['href'] if link_elem else ''
                if url and not url.startswith('http'):
                    url = 'https://onefootball.com' + url

                time_elem = article.select_one('time, [class*="date"]')
                publish_time = parse_publish_time(time_elem['datetime'] if time_elem and time_elem.get('datetime') else '')

                if since_time and publish_time < since_time:
                    logger.info(f"Новость '{title[:50]}...' старая, пропускаем")
                    continue

                # Попытка взять миниатюру с превью-страницы (чтобы снизить риск перепутать изображения)
                thumb_img = article.select_one('img')
                thumb_url = ''
                if thumb_img and thumb_img.get('src'):
                    thumb_url = thumb_img['src']
                    if thumb_url and not thumb_url.startswith('http'):
                        thumb_url = 'https://onefootball.com' + thumb_url

                # Извлечение полного текста и изображения (если в статье не будет картинки, используем миниатюру)
                article_text, image_url = fetch_full_article(url)
                if not image_url and thumb_url:
                    image_url = thumb_url
                translated_title = create_enhanced_summary({
                    'title': title,
                    'content': article_text,
                    'url': url,
                    'source': 'OneFootball'
                }).strip()

                # Удаляем markdown-выделение ** вокруг подзаголовков, если AI вернул их
                if translated_title.startswith('**') and translated_title.endswith('**'):
                    translated_title = translated_title.strip('* ').strip()
                # Также чистим контент от остаточных '**'
                if article_text:
                    article_text = article_text.replace('**', '')

                news_item = {
                    'title': translated_title,
                    'url': url,
                    'content': article_text,
                    'publish_time': publish_time,
                    'image_url': image_url,
                    'source': 'OneFootball'
                }
                news_items.append(news_item)
                logger.info(f"Добавлена новость: {translated_title[:50]}...")
            except Exception as e:
                logger.error(f"Ошибка обработки новости: {e}")
                continue

        logger.info(f"Найдено {len(news_items)} новых новостей с OneFootball")
        return news_items

    except Exception as e:
        logger.error(f"Ошибка получения новостей с OneFootball: {e}")
        return []

