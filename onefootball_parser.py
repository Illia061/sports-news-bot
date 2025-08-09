import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
import random
import time
import re
import os  # Импорт os для совместимости с ai_processor.py
from typing import List, Dict, Any, Optional
from bs4 import Tag
from ai_processor import process_article_for_posting  # Импорт функции из ai_processor.py

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

class OneFootballTargetedParser:
    def __init__(self):
        self.base_url = CONFIG['BASE_URL']
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(CONFIG['USER_AGENTS']),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        })

    def get_page_content(self, url: str) -> Optional[BeautifulSoup]:
        """Загружает содержимое страницы."""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            logger.error(f"Ошибка загрузки страницы {url}: {e}")
            return None

    def find_latest_news_section(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Находит блок с последними новостями (аналог 'ГОЛОВНЕ ЗА ДОБУ')."""
        header_texts = [
            "Latest", "Top News", "News", "Feed", "Recent", "Breaking News"
        ]

        for header_text in header_texts:
            header_element = soup.find(text=re.compile(header_text, re.I))
            if header_element:
                logger.info(f"✅ Найден заголовок: '{header_text}'")
                parent = header_element.parent
                while parent and parent.name not in ['section', 'div', 'article', 'ul']:
                    parent = parent.parent
                if parent:
                    news_container = parent.find_next(['div', 'ul', 'section', 'article'])
                    if news_container:
                        logger.info(f"✅ Найден контейнер новостей после заголовка")
                        return news_container
                    return parent

        # Дополнительные селекторы для OneFootball
        possible_selectors = [
            '[data-testid="feed"]', '[data-testid="home-feed"]', '[data-testid="news-feed"]',
            '.feed', '.news-feed', '.latest-news', '.article-list', '.home-feed',
            '[class*="feed"]', '[class*="news"]', '[class*="latest"]', '[class*="article"]'
        ]

        for selector in possible_selectors:
            elements = soup.select(selector)
            for element in elements:
                if re.search(r'(latest|news|feed|top|recent|breaking)', element.get_text().lower()):
                    logger.info(f"✅ Найден блок через селектор: {selector}")
                    return element

        # Fallback на общий поиск
        logger.warning("⚠️ Основной блок не найден, ищем общий контейнер с новостями")
        all_sections = soup.find_all(['section', 'div'], class_=True)
        for section in all_sections:
            section_text = section.get_text().lower()
            if any(word in section_text for word in ['news', 'latest', 'feed', 'top']):
                logger.info(f"✅ Найден потенциальный блок новостей")
                return section

        logger.warning("❌ Блок с новостями не найден")
        return None

    def extract_news_from_section(self, section: Tag, since_time: datetime = None) -> List[Dict[str, Any]]:
        """Извлекает новости из найденного блока с фильтрацией по времени."""
        if not section:
            return []

        news_links = []
        all_links = section.find_all('a', href=True)
        logger.info(f"🔍 Найдено {len(all_links)} ссылок в блоке")

        for link in all_links:
            href = link.get('href', '')
            title = link.get_text(strip=True)
            if self.is_news_link(href) and len(title) > 20:
                full_url = 'https://onefootball.com' + href if href.startswith('/') else href
                news_links.append({
                    'title': title,
                    'url': full_url
                })
                logger.info(f"📰 Найдена новость: {title[:50]}...")

        # Убираем дубликаты
        unique_news = list({news['url']: news for news in news_links}.values())
        return unique_news[:CONFIG['MAX_NEWS']]

    def is_news_link(self, href: str) -> bool:
        """Проверяет, является ли ссылка новостной."""
        return 'news' in href or 'article' in href or 'story' in href

    def get_full_article_data(self, news_item: Dict[str, Any], since_time: datetime = None) -> Optional[Dict[str, Any]]:
        """Получает полный контент статьи, проверяет время и возвращает данные."""
        url = news_item['url']
        logger.info(f"📖 Загружаем статью: {url}")
        soup = self.get_page_content(url)
        if not soup:
            return None

        # Извлечение времени публикации
        time_str = self.extract_publish_time(soup)
        publish_time = parse_publish_time(time_str)
        if since_time and publish_time < since_time:
            logger.info(f"🚫 Новость старая: {publish_time} < {since_time}")
            return None

        # Извлечение контента
        article_text = self.extract_article_text(soup)

        # Извлечение изображения
        image_url = self.extract_article_image(soup, url)

        # Подготовка статьи для обработки
        article_data = {
            'title': news_item['title'],
            'url': url,
            'content': article_text,
            'summary': article_text[:300] + "..." if len(article_text) > 300 else article_text,
            'image_url': image_url,
            'source': 'OneFootball',
            'original_title': news_item['title'],
            'original_content': article_text,
            'publish_time': publish_time
        }

        # Обработка статьи с AI
        try:
            processed_article = process_article_for_posting(article_data)
            translated_title = processed_article.get('title', news_item['title'])
            processed_content = processed_article.get('processed_content', article_text)
            summary = processed_article.get('summary', article_data['summary'])
        except Exception as e:
            logger.error(f"Ошибка при обработке статьи {url}: {e}")
            translated_title = news_item['title']
            processed_content = article_text
            summary = article_data['summary']

        return {
            'title': translated_title,
            'url': url,
            'link': url,  # Для совместимости с main.py
            'content': article_text,  # Оригинальный текст
            'summary': summary,
            'publish_time': publish_time,
            'image_url': image_url,
            'source': 'OneFootball',
            'original_title': news_item['title'],
            'original_content': article_text,
            'processed_content': processed_content
        }

    def extract_publish_time(self, soup: BeautifulSoup) -> str:
        """Извлекает строку времени из статьи."""
        time_selectors = [
            'time[datetime]', '[data-testid="date"]', '.date', '.publish-date',
            '[class*="date"]', '[class*="time"]'
        ]
        for selector in time_selectors:
            time_elem = soup.select_one(selector)
            if time_elem:
                return time_elem.get('datetime', time_elem.get_text(strip=True))
        return str(datetime.now(KIEV_TZ))

    def extract_article_text(self, soup: BeautifulSoup) -> str:
        """Извлекает текст статьи."""
        content_selectors = [
            '[data-testid="article-body"]', '.ArticleBody', '.article-body',
            '.article-content', '.post-content', '[class*="body"]', '[class*="content"]',
            'article', '.main-text', '.content'
        ]
        article_text = ""
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                for unwanted in content_div.find_all(['script', 'style', 'iframe', 'div[class*="ad"]', 'aside', 'nav']):
                    unwanted.decompose()
                paragraphs = content_div.find_all('p')
                if paragraphs:
                    meaningful_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
                    article_text = '\n'.join(meaningful_paragraphs)
                else:
                    article_text = content_div.get_text(strip=True)
                if len(article_text) > 100:
                    break
        if not article_text:
            all_paragraphs = soup.find_all('p')
            article_text = ' '.join(p.get_text(strip=True) for p in all_paragraphs if len(p.get_text(strip=True)) > 50)
        return article_text

    def extract_article_image(self, soup: BeautifulSoup, base_url: str) -> str:
        """Извлекает URL изображения из статьи."""
        image_selectors = [
            'meta[property="og:image"]', 'meta[name="twitter:image"]',
            '[data-testid="article-image"]', '.article-image img',
            'img[alt*="article"]', '.featured-image img', '.main-image img'
        ]
        for selector in image_selectors:
            img_elem = soup.select_one(selector)
            if img_elem:
                image_url = img_elem.get('content', '') or img_elem.get('src', '') or img_elem.get('data-src', '')
                if image_url:
                    if not image_url.startswith('http'):
                        image_url = 'https://onefootball.com' + image_url if image_url.startswith('/') else 'https://' + image_url
                    if not any(small in image_url.lower() for small in ['icon', 'logo', 'thumb', 'avatar']):
                        return image_url
        return ''

    def get_latest_news(self, since_time: datetime = None) -> List[Dict[str, Any]]:
        """Получает последние новости с фильтрацией по времени."""
        logger.info("Получение новостей с OneFootball...")
        soup = self.get_page_content(self.base_url)
        if not soup:
            return []

        news_section = self.find_latest_news_section(soup)
        if not news_section:
            return []

        news_items = self.extract_news_from_section(news_section, since_time)

        full_articles = []
        current_time = datetime.now(KIEV_TZ)
        if since_time is None:
            current_hour = current_time.hour
            current_minute = current_time.minute
            if 5 <= current_hour < 6 and current_minute >= 50 or current_hour == 6 and current_minute <= 10:
                since_time = current_time.replace(hour=1, minute=0, second=0, microsecond=0)
                logger.info(f"Режим 5 часов: since_time установлено на {since_time}")
            else:
                since_time = current_time - timedelta(minutes=20)
                logger.info(f"Режим 20 минут: since_time установлено на {since_time}")

        for news_item in news_items:
            article_data = self.get_full_article_data(news_item, since_time)
            if article_data is None:
                break  # Прекращаем, если встретили старую новость
            if article_data:
                full_articles.append(article_data)
            time.sleep(1)  # Пауза

        logger.info(f"Найдено {len(full_articles)} новых новостей с OneFootball")
        return full_articles

def parse_publish_time(time_str: str, current_time: datetime = None) -> datetime:
    """Преобразует строку времени в datetime с киевским временем."""
    if not current_time:
        current_time = datetime.now(KIEV_TZ)
    try:
        if 'ago' in time_str.lower():
            value = int(''.join(filter(str.isdigit, time_str)))
            unit = 'minutes' if 'minute' in time_str else 'hours' if 'hour' in time_str else 'days'
            delta = timedelta(minutes=value) if unit == 'minutes' else timedelta(hours=value) if unit == 'hours' else timedelta(days=value)
            return current_time - delta
        if 'T' in time_str:
            return datetime.fromisoformat(time_str.replace('Z', '+00:00')).astimezone(KIEV_TZ)
        try:
            return datetime.strptime(time_str, '%Y-%m-%d %H:%M %Z').astimezone(KIEV_TZ)
        except ValueError:
            return datetime.strptime(time_str, '%Y-%m-%d %H:%M').replace(tzinfo=KIEV_TZ)
    except Exception as e:
        logger.warning(f"Ошибка парсинга времени '{time_str}': {e}")
        return current_time

# Функция для совместимости с main.py
def get_latest_news(since_time: datetime = None) -> List[Dict[str, Any]]:
    """Функция-обертка для совместимости с main.py."""
    parser = OneFootballTargetedParser()
    articles = parser.get_latest_news(since_time)
    # Конвертируем в формат, ожидаемый main.py
    result = []
    for article in articles:
        result.append({
            'title': article['title'],
            'link': article['url'],  # main.py ожидает 'link'
            'url': article['url'],   # Для ai_processor
            'summary': article['summary'],
            'image_url': article['image_url'],
            'content': article['content'],  # Полный контент для AI
            'publish_time': article.get('publish_time'),
            'source': article['source'],
            'original_title': article.get('original_title', ''),
            'original_content': article.get('original_content', ''),
            'processed_content': article.get('processed_content', '')
        })
    return result
