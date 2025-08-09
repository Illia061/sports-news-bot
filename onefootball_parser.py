import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
import random
import time
import os
import google.generativeai as genai
import json

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

class OneFootballParser:
    def __init__(self):
        self.base_url = CONFIG['BASE_URL']
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(CONFIG['USER_AGENTS']),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,uk;q=0.8",
            "Connection": "keep-alive",
            "Referer": "https://onefootball.com/",
        })
        
        # Инициализация Gemini
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.model = None
        self.init_gemini()

    def init_gemini(self):
        """Инициализирует клиента Gemini."""
        if not self.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY не найден - AI функции отключены")
            return
        try:
            genai.configure(api_key=self.GEMINI_API_KEY)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
            logger.info("Gemini инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации Gemini: {e}")

    def parse_publish_time(self, time_str: str, current_time: datetime = None) -> datetime:
        """Преобразует строку времени в объект datetime с киевским часовым поясом (EEST)."""
        try:
            if not current_time:
                current_time = datetime.now(KIEV_TZ)
            logger.debug(f"Попытка парсинга времени: {time_str}, текущее время: {current_time}")

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
            return current_time

    def get_page_content(self, url: str) -> BeautifulSoup:
        """Получает содержимое страницы через статический парсинг."""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            with open('onefootball_static.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            logger.error(f"Ошибка загрузки {url}: {e}")
            return None

    def find_top_news_section(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Находит секцию с верхними новостями."""
        possible_selectors = [
            '.of-feed',
            '[data-testid="feed"]',
            '.news-feed',
            '.latest-articles',
            '.article-feed',
            '[data-testid="news-list"]',
            '[class*="feed"]',
            '[class*="news"]',
            '[class*="articles"]'
        ]

        for selector in possible_selectors:
            section = soup.select_one(selector)
            if section:
                logger.info(f"✅ Найден блок новостей через селектор: {selector}")
                return section

        all_divs = soup.find_all('div', class_=True)
        for div in all_divs:
            class_str = str(div.get('class', ''))
            if any(bad in class_str.lower() for bad in ['banner', 'promo', 'advert', 'sponsored', 'teaser']):
                continue
            if re.search(r'news|articles|feed|latest|content', class_str, re.I):
                logger.info(f"✅ Найден блок новостей через анализ структуры: {class_str}")
                return div

        logger.error("❌ Секция новостей не найдена")
        return None

    def fetch_full_article(self, url: str) -> tuple[str, str]:
        """Извлекает полный текст и изображение из статьи."""
        try:
            soup = self.get_page_content(url)
            if not soup:
                return "", ""

            content_selectors = [
                '.article-content',
                '.post-content',
                '[class*="body"]',
                'article',
                '.main-text',
                '.content'
            ]

            article_text = ""
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    for unwanted in content_div.find_all(['script', 'style', 'iframe', 'div[class*="ad"]']):
                        unwanted.decompose()
                    paragraphs = content_div.find_all('p')
                    if paragraphs:
                        article_text = '\n'.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])
                        break
                    else:
                        article_text = content_div.get_text(strip=True)
                        break

            if not article_text:
                all_paragraphs = soup.find_all('p')
                meaningful_paragraphs = []
                for p in all_paragraphs:
                    text = p.get_text(strip=True)
                    if (len(text) > 30 and
                        not any(skip in text.lower() for skip in ['cookie', 'advertisement', 'subscribe', 'photo', 'source'])):
                        meaningful_paragraphs.append(text)
                article_text = '\n'.join(meaningful_paragraphs)
                if len(article_text) > 1500:
                    sentences = re.split(r'[.!?]+', article_text)
                    trimmed_content = ""
                    current_length = 0
                    for sentence in sentences:
                        if current_length + len(sentence) <= 1500:
                            trimmed_content += sentence + '. '
                            current_length += len(sentence) + 2
                        else:
                            break
                    article_text = trimmed_content.rstrip()

            image_selectors = [
                'meta[property="og:image"]',
                'meta[name="twitter:image"]',
                '.article-content img:first-of-type',
                '.main-image img',
                '.post-image img',
                'img[class*="featured"]'
            ]

            image_url = ""
            for selector in image_selectors:
                img_elem = soup.select_one(selector)
                if img_elem:
                    image_url = img_elem.get('content', '') or img_elem.get('src', '') or img_elem.get('data-src', '')
                    if image_url:
                        image_url = urljoin(url, image_url)
                        if not any(small in image_url.lower() for small in ['icon', 'logo', 'thumb', 'avatar']):
                            break
            return article_text, image_url

        except Exception as e:
            logger.error(f"Ошибка загрузки статьи {url}: {e}")
            return "", ""

    def translate_and_process_article(self, title: str, content: str, url: str) -> tuple[str, str]:
        """Переводит и создает краткое резюме статьи с использованием Gemini."""
        if not self.model:
            logger.warning("Gemini недоступен, возвращаем исходные данные")
            return title, content[:200] + "..." if len(content) > 200 else content

        prompt = f"""Ти редактор футбольних новин. Переклади заголовок і текст статті з англійської на українську мову, потім створи КОРОТКИЙ пост для Telegram (макс. 150 слів).

Правила перекладу:
- Зберігай точність футбольної термінології
- Уникай дослівного перекладу, адаптуй до природної української мови
- Зберігай імена гравців і команд без змін

Правила посту:
- Тільки ключові факти
- Максимум 1-2 речення прямої мови
- Для рейтингів: лише топ-5
- Структура: головний факт (1-2 речення), деталі (2-4 речення)

Заголовок: {title}
Текст: {content[:1500]}

ВІДПОВІДЬ У ФОРМАТІ JSON:
{{
    "translated_title": "...",
    "summary": "..."
}}
"""
        try:
            response = self.model.generate_content(prompt)
            result = response.text.strip()
            parsed = json.loads(result)
            return parsed['translated_title'], parsed['summary']
        except Exception as e:
            logger.error(f"Ошибка обработки Gemini для {url}: {e}")
            return title, content[:200] + "..." if len(content) > 200 else content

    def get_latest_news(self, since_time: datetime = None) -> list:
        """Получает последние новости с OneFootball с фильтрацией по времени и полной обработкой статей."""
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

        logger.info(f"🔍 Загружаем главную страницу OneFootball... (с {since_time.strftime('%H:%M %d.%m.%Y')})")

        soup = self.get_page_content(self.base_url)
        if not soup:
            logger.error("❌ Не удалось загрузить главную страницу")
            return []

        news_container = self.find_top_news_section(soup)
        if not news_container:
            logger.error("❌ Секция новостей не найдена")
            return []

        articles = news_container.find_all(['article', 'div', 'li', 'section'], recursive=True)[:CONFIG['MAX_NEWS']]
        logger.info(f"🔍 Найдено {len(articles)} элементов в секции")

        news_items = []
        for article in articles:
            try:
                title_elem = article.select_one('h1, h2, h3, [class*="title"], [class*="headline"]')
                title = title_elem.get_text(strip=True) if title_elem else ''
                if not title or len(title) < 10:
                    continue

                link_elem = article.select_one('a[href]')
                url = link_elem['href'] if link_elem else ''
                if not url:
                    continue
                if not url.startswith('http'):
                    url = urljoin(self.base_url, url)

                time_elem = article.select_one('time, [class*="date"], [class*="time"]')
                time_str = time_elem['datetime'] if time_elem and 'datetime' in time_elem.attrs else ''
                if not time_str:
                    time_text = time_elem.get_text(strip=True) if time_elem else ''
                    time_str = time_text if time_text else str(current_time)
                logger.debug(f"Извлечено время новости: {time_str}")

                publish_time = self.parse_publish_time(time_str, current_time)
                if publish_time < since_time:
                    logger.info(f"Новость '{title[:50]}...' старая, пропускаем (publish_time={publish_time}, since_time={since_time})")
                    continue

                article_text, image_url = self.fetch_full_article(url)
                if not image_url:
                    thumb_img = article.select_one('img')
                    if thumb_img:
                        thumb_url = thumb_img.get('src', '') or thumb_img.get('data-src', '')
                        if thumb_url:
                            image_url = urljoin(self.base_url, thumb_url) if not thumb_url.startswith('http') else thumb_url

                translated_title, processed_content = self.translate_and_process_article(title, article_text, url)

                news_item = {
                    'title': translated_title,
                    'url': url,
                    'content': processed_content,
                    'summary': processed_content[:300] + "..." if len(processed_content) > 300 else processed_content,
                    'publish_time': publish_time,
                    'image_url': image_url,
                    'source': 'OneFootball',
                    'original_title': title,
                    'original_content': article_text
                }
                news_items.append(news_item)
                logger.info(f"📰 Добавлена новость: {translated_title[:50]}...")

                time.sleep(1)

            except Exception as e:
                logger.error(f"Ошибка обработки новости: {e}")
                continue

        logger.info(f"✅ Найдено {len(news_items)} новых новостей с OneFootball")
        return news_items

def get_latest_news(since_time: datetime = None) -> list:
    """Функция-обертка для совместимости с main.py."""
    parser = OneFootballParser()
    return parser.get_latest_news(since_time)

if __name__ == "__main__":
    logger.info("🎯 ТЕСТИРУЕМ ПАРСЕР ДЛЯ ONEFOOTBALL")
    logger.info("=" * 60)
    articles = get_latest_news()
    if articles:
        logger.info(f"✅ Найдено {len(articles)} новостей")
        for i, article in enumerate(articles, 1):
            publish_time = article.get('publish_time')
            time_str = publish_time.strftime('%H:%M %d.%m') if publish_time else 'неизвестно'
            logger.info(f"   📰 {i}. {article['title'][:50]}... ({time_str})")
    else:
        logger.info("📭 Новостей не найдено")
