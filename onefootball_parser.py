import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
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

def parse_publish_time(time_str: str, current_time: datetime = None) -> datetime:
    """Преобразует строку времени в объект datetime с киевским часовым поясом (EEST).
    Поддерживает относительное время (например, '15 minutes ago') и ISO формат."""
    try:
        if not current_time:
            current_time = datetime.now(KIEV_TZ)
        logger.debug(f"Попытка парсинга времени: {time_str}, текущее время: {current_time}")

        # Проверка на относительное время (например, '15 minutes ago')
        if 'ago' in time_str.lower():
            for unit in ['minutes', 'hours', 'days']:
                if unit in time_str.lower():
                    value = int(''.join(filter(str.isdigit, time_str)))
                    if unit == 'minutes':
                        delta = timedelta(minutes=value)
                    elif unit == 'hours':
                        delta = timedelta(hours=value)
                    elif unit == 'days':
                        delta = timedelta(days=value)
                    return current_time - delta
            raise ValueError("Не удалось распознать относительное время")

        # Проверка на ISO формат (например, '2025-08-08T18:02:00Z')
        if 'T' in time_str:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00')).astimezone(KIEV_TZ)
        else:
            try:
                dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M %Z').astimezone(KIEV_TZ)
            except ValueError:
                dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M').replace(tzinfo=KIEV_TZ)
        logger.debug(f"Успешно распарсено время: {time_str} -> {dt}")
        return dt
    except Exception as e:
        logger.warning(f"Ошибка парсинга времени '{time_str}': {e}")
        return current_time  # Возвращаем текущее время в случае ошибки

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

        current_time = datetime.now(KIEV_TZ)
        for article in news_container[:CONFIG['MAX_NEWS']]:
            try:
                title_elem = article.select_one('h3, [class*="title"]')
                title = title_elem.get_text(strip=True) if title_elem else ''

                link_elem = article.select_one('a[href]')
                url = link_elem['href'] if link_elem else ''
                if url and not url.startswith('http'):
                    url = 'https://onefootball.com' + url

                time_elem = article.select_one('time, [class*="date"]')
                time_str = time_elem['datetime'] if time_elem and 'datetime' in time_elem.attrs else ''
                if not time_str:  # Если datetime отсутствует, попробуем извлечь из текста
                    time_text = time_elem.get_text(strip=True) if time_elem else ''
                    time_str = time_text if time_text else str(current_time)
                logger.debug(f"Извлечено время новости: {time_str}")

                publish_time = parse_publish_time(time_str, current_time)

                if since_time and publish_time < since_time:
                    logger.info(f"Новость '{title[:50]}...' старая, пропускаем (publish_time={publish_time}, since_time={since_time})")
                    continue

                thumb_img = article.select_one('img')
                thumb_url = thumb_img['src'] if thumb_img and 'src' in thumb_img.attrs else ''
                if thumb_url and not thumb_url.startswith('http'):
                    thumb_url = 'https://onefootball.com' + thumb_url

                article_text, image_url = fetch_full_article(url)
                if not image_url and thumb_url:
                    image_url = thumb_url
                translated_title = create_enhanced_summary({
                    'title': title,
                    'content': article_text,
                    'url': url,
                    'source': 'OneFootball'
                }).strip()

                if translated_title.startswith('**') and translated_title.endswith('**'):
                    translated_title = translated_title.strip('* ').strip()
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
                news_items.append(newitem)
                logger.info(f"Добавлена новость: {translated_title[:50]}...")
            except Exception as e:
                logger.error(f"Ошибка обработки новости: {e}")
                continue

        logger.info(f"Найдено {len(news_items)} новых новостей с OneFootball")
        return news_items

    except Exception as e:
        logger.error(f"Ошибка получения новостей с OneFootball: {e}")
        return []

