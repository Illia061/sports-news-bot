import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import random

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
    'MAX_NEWS': 20
}

KIEV_TZ = ZoneInfo("Europe/Kiev")

def parse_publish_time(time_str: str) -> datetime:
    """Преобразует строку времени в объект datetime с киевским часовым поясом."""
    try:
        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M %Z')
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("Europe/Kiev"))
        return dt.astimezone(KIEV_TZ)
    except Exception as e:
        logger.warning(f"Ошибка парсинга времени '{time_str}': {e}")
        return datetime.now(KIEV_TZ)

def get_latest_news(since_time: datetime = None) -> list:
    """Получает последние новости с OneFootball."""
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

                summary_elem = article.select_one('p, [class*="description"], [class*="summary"]')
                summary = summary_elem.get_text(strip=True) if summary_elem else ''

                time_elem = article.select_one('time, [class*="date"]')
                publish_time = parse_publish_time(time_elem['datetime'] if time_elem and time_elem.get('datetime') else '')
                
                img_elem = article.select_one('img[src]')
                image_url = img_elem['src'] if img_elem else ''

                if since_time and publish_time < since_time:
                    logger.info(f"Новость '{title[:50]}...' старая, пропускаем")
                    continue

                news_item = {
                    'title': title,
                    'url': url,
                    'summary': summary,
                    'publish_time': publish_time,
                    'image_url': image_url,
                    'source': 'OneFootball'
                }
                news_items.append(news_item)
                logger.info(f"Добавлена новость: {title[:50]}...")
            except Exception as e:
                logger.error(f"Ошибка обработки новости: {e}")
                continue

        logger.info(f"Найдено {len(news_items)} новых новостей с OneFootball")
        return news_items

    except Exception as e:
        logger.error(f"Ошибка получения новостей с OneFootball: {e}")
        return []