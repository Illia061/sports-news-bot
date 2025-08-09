import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo
import google.generativeai as genai
import logging
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

KIEV_TZ = ZoneInfo("Europe/Kiev")

class OneFootballParser:
    def __init__(self):
        self.base_url = "https://onefootball.com/en/home"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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

    def get_page_content(self, url: str) -> Optional[BeautifulSoup]:
        """Получает содержимое страницы через статический парсинг."""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            with open('onefootball_static.html', 'w', encoding='utf-8') as f:
                f.write(response.text)  # Сохраняем HTML для анализа
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            logger.error(f"Ошибка загрузки {url}: {e}")
            return None

    def find_top_news_section(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
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
            '[class*="articles"]',
        ]

        for selector in possible_selectors:
            section = soup.select_one(selector)
            if section:
                logger.info(f"✅ Найден блок новостей через селектор: {selector}")
                return section

        # Резервный поиск: все div с классами, содержащими новости
        all_divs = soup.find_all('div', class_=True)
        for div in all_divs:
            class_str = str(div.get('class', ''))
            if any(bad in class_str.lower() for bad in ['banner', 'promo', 'advert', 'sponsored']):
                continue  # Пропускаем рекламные блоки
            if re.search(r'news|articles|feed|latest|content', class_str, re.I):
                logger.info(f"✅ Найден блок новостей через анализ структуры: {class_str}")
                return div

        logger.error("❌ Секция новостей не найдена")
        return None

    def extract_news_from_section(self, section: BeautifulSoup, max_items: int = 10) -> List[Dict[str, Any]]:
        """Извлекает до 10 новостей из секции."""
        if not section:
            return []

        news_links = []
        articles = section.find_all(['article', 'div', 'li', 'section'], recursive=True)[:max_items]

        logger.info(f"🔍 Найдено {len(articles)} элементов в секции")

        for article in articles:
            link = article.find('a', href=True)
            if not link:
                continue

            href = link.get('href', '')
            title_elem = link.find(['h1', 'h2', 'h3', 'span', 'div'], class_=re.compile(r'title|headline|text', re.I))
            title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)

            if not title or len(title) < 10 or not self.is_news_link(href):
                continue

            full_url = urljoin(self.base_url, href)
            news_links.append({
                'title': title,
                'url': full_url,
                'href': href
            })
            logger.info(f"📰 Найдена новость: {title[:50]}...")

        # Убираем дубликаты по URL
        seen_urls = set()
        unique_news = []
        for news in news_links:
            if news['url'] not in seen_urls:
                seen_urls.add(news['url'])
                unique_news.append(news)

        return unique_news[:max_items]

    def is_news_link(self, href: str) -> bool:
        """Проверяет, является ли ссылка новостной."""
        if not href:
            return False
        return (
            href.startswith('/') or
            href.startswith(self.base_url) or
            'news' in href.lower() or
            'article' in href.lower()
        ) and not any(ext in href.lower() for ext in ['login', 'signup', 'profile', '#'])

    def get_article_publish_time(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Извлекает время публикации статьи."""
        time_selectors = [
            'time[datetime]',
            '.date',
            '.publish-date',
            '[class*="date"]',
            '[class*="time"]',
            'meta[property="article:published_time"]',
            'meta[name="pubdate"]'
        ]

        for selector in time_selectors:
            time_elem = soup.select_one(selector)
            if time_elem:
                time_str = time_elem.get('datetime') or time_elem.get('content') or time_elem.get_text(strip=True)
                try:
                    pub_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    return pub_time.astimezone(KIEV_TZ)
                except ValueError:
                    try:
                        pub_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                        return pub_time.replace(tzinfo=KIEV_TZ)
                    except ValueError:
                        continue
        return None

    def get_article_content(self, soup: BeautifulSoup) -> str:
        """Извлекает основной текст статьи."""
        content_selectors = [
            '.article-content',
            '.post-content',
            '.entry-content',
            '[class*="content"]',
            '.article-body',
            '.post-body',
            '.story-body'
        ]

        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                for unwanted in content_div.find_all(['script', 'style', 'iframe', 'ads', 'aside']):
                    unwanted.decompose()
                content = content_div.get_text(strip=True)
                if content and len(content) > 50:
                    return content[:2000]

        paragraphs = soup.find_all('p')
        content = ' '.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        return content[:2000] if content else ""

    def get_article_image(self, soup: BeautifulSoup, base_url: str) -> str:
        """Извлекает URL главного изображения статьи."""
        image_selectors = [
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
            '.article-content img:first-of-type',
            '.main-image img',
            '.post-image img'
        ]

        for selector in image_selectors:
            img_elem = soup.select_one(selector)
            if img_elem:
                image_url = img_elem.get('content', '') or img_elem.get('src', '') or img_elem.get('data-src', '')
                if image_url:
                    full_image_url = urljoin(base_url, image_url)
                    if not any(small in image_url.lower() for small in ['icon', 'logo', 'thumb', 'avatar']):
                        return full_image_url
        return ""

    def translate_and_summarize(self, title: str, content: str) -> Dict[str, str]:
        """Переводит и создает краткое резюме статьи с использованием Gemini."""
        if not self.model:
            logger.warning("Gemini недоступен, возвращаем исходный заголовок")
            return {'translated_title': title, 'summary': title[:200]}

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
            import json
            return json.loads(result)
        except Exception as e:
            logger.error(f"Ошибка обработки Gemini: {e}")
            return {'translated_title': title, 'summary': content[:200]}

    def get_full_article_data(self, news_item: Dict[str, Any], since_time: Optional[datetime]) -> Optional[Dict[str, Any]]:
        """Получает полные данные статьи, включая перевод и резюме."""
        url = news_item['url']
        logger.info(f"📖 Загружаем статью: {url}")

        soup = self.get_page_content(url)
        if not soup:
            logger.error(f"❌ Не удалось загрузить статью: {url}")
            return None

        publish_time = self.get_article_publish_time(soup)
        if since_time and publish_time and publish_time < since_time:
            logger.info(f"🛑 Статья слишком старая: {publish_time.strftime('%H:%M %d.%m')}")
            return None

        content = self.get_article_content(soup)
        image_url = self.get_article_image(soup, url)
        ai_result = self.translate_and_summarize(news_item['title'], content)

        return {
            'title': ai_result['translated_title'],
            'original_title': news_item['title'],
            'url': url,
            'summary': ai_result['summary'],
            'content': content,
            'image_url': image_url,
            'publish_time': publish_time,
            'source': 'OneFootball'
        }

    def get_latest_news(self, since_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Основной метод - получает верхние 10 новостей с фильтрацией по времени."""
        current_time_kiev = datetime.now(KIEV_TZ)
        is_morning = (5*60 + 50 <= current_time_kiev.hour*60 + current_time_kiev.minute <= 6*60 + 10)
        time_delta = timedelta(hours=5) if is_morning else timedelta(minutes=20)
        since_time = since_time or (current_time_kiev - time_delta)

        logger.info(f"🔍 Загружаем главную страницу OneFootball... (с {since_time.strftime('%H:%M %d.%m.%Y')})")

        soup = self.get_page_content(self.base_url)
        if not soup:
            logger.error("❌ Не удалось загрузить главную страницу")
            return []

        news_section = self.find_top_news_section(soup)
        if not news_section:
            logger.error("❌ Секция новостей не найдена")
            return []

        news_items = self.extract_news_from_section(news_section, max_items=10)
        if not news_items:
            logger.error("❌ Новости не найдены")
            return []

        logger.info(f"✅ Найдено {len(news_items)} новостей")

        full_articles = []
        for i, news_item in enumerate(news_items, 1):
            logger.info(f"📖 Обрабатываем новость {i}/{len(news_items)}: {news_item['title'][:50]}...")
            article_data = self.get_full_article_data(news_item, since_time)
            if article_data:
                full_articles.append(article_data)
            time.sleep(1)  # Пауза между запросами

        logger.info(f"✅ Обработано {len(full_articles)} новых статей")
        return full_articles

def get_latest_news(since_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Функция-обертка для совместимости с main.py."""
    parser = OneFootballParser()
    articles = parser.get_latest_news(since_time)
    return [{
        'title': article['title'],
        'link': article['url'],
        'url': article['url'],
        'summary': article['summary'],
        'image_url': article['image_url'],
        'content': article['content'],
        'publish_time': article['publish_time'],
        'source': 'OneFootball',
        'original_title': article['original_title']
    } for article in articles]

def test_onefootball_parser():
    """Тестирование парсера OneFootball."""
    logger.info("🎯 ТЕСТИРУЕМ ПАРСЕР ДЛЯ ONEFOOTBALL")
    logger.info("=" * 60)

    # Тест 1: Получение всех новостей
    logger.info("\n📋 Тест 1: Получение всех новостей")
    parser = OneFootballParser()
    articles = parser.get_latest_news()

    if articles:
        logger.info(f"✅ Найдено {len(articles)} новостей")
        for i, article in enumerate(articles, 1):
            publish_time = article.get('publish_time')
            time_str = publish_time.strftime('%H:%M %d.%m') if publish_time else 'неизвестно'
            logger.info(f"   📰 {i}. {article['title'][:50]}... ({time_str})")
    else:
        logger.info("📭 Новостей не найдено")

    # Тест 2: Получение новостей с фильтрацией по времени
    logger.info("\n📋 Тест 2: Получение новостей за последние 20 минут")
    since_time = datetime.now(KIEV_TZ) - timedelta(minutes=20)
    recent_articles = parser.get_latest_news(since_time)

    if recent_articles:
        logger.info(f"✅ Найдено {len(recent_articles)} новых новостей")
        for i, article in enumerate(recent_articles, 1):
            publish_time = article.get('publish_time')
            time_str = publish_time.strftime('%H:%M %d.%m') if publish_time else 'неизвестно'
            logger.info(f"   📰 {i}. {article['title'][:50]}... ({time_str})")
    else:
        logger.info("📭 Новых новостей за последние 20 минут не найдено")

if __name__ == "__main__":
    test_onefootball_parser()
