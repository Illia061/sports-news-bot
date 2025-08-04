import asyncio
import re
import logging
import random
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Playwright не установлен. Установите: pip install playwright")
    print("Затем выполните: playwright install")

from ai_processor import has_gemini_key, model as gemini_model

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

KIEV_TZ = ZoneInfo("Europe/Kiev")

# Конфигурация
CONFIG = {
    'BASE_URL': "https://www.besoccer.com/news/latest",
    'PAGE_TIMEOUT': 30000,  # 30 секунд
    'NAVIGATION_TIMEOUT': 20000,  # 20 секунд
    'REQUEST_DELAY': (2, 5),  # Случайная задержка между запросами
    'MAX_NEWS_ITEMS': 8,
    'HEADLESS': True,  # Установите False для отладки
    'SOCCER_PATTERNS': [
        r'/news/', r'/match/', r'/player/', r'/team/', r'/competition/',
        r'premier-league', r'champions-league', r'la-liga', r'serie-a',
        r'bundesliga', r'ligue-1', r'mls', r'uefa', r'fifa'
    ],
    'EXCLUDE_PATTERNS': [
        r'/video/', r'/live-score/', r'/stats/', r'/standings/',
        r'/schedule/', r'/betting/', r'/fantasy/', r'#',
        r'javascript:', r'mailto:', r'/podcast/'
    ],
    'CONTENT_SELECTORS': [
        '.news-detail', '.article-body', '.story-content',
        '[class*="content"]', '.post-content', '.news-content'
    ],
    'IMAGE_SELECTORS': [
        'meta[property="og:image"]', '.news-image img',
        '.article-figure img', '.hero-image img', '.featured-image img',
        'figure img:first-of-type'
    ],
    'TIME_SELECTORS': [
        'time[datetime]', '.news-date', '.publish-date',
        '.article-meta time', '[data-date]', '[class*="time"]',
        '[class*="date"]'
    ],
    'META_TIME_SELECTORS': [
        'meta[property="article:published_time"]',
        'meta[name="publish_date"]', 'meta[property="og:published_time"]'
    ],
    'EXCLUDE_IMAGE_KEYWORDS': ['logo', 'icon', 'banner', 'advertisement', 'thumb', '/16x', '/32x']
}

class BeSoccerPlaywrightParser:
    def __init__(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright не установлен. Выполните: pip install playwright && playwright install")
        
        self.base_url = CONFIG['BASE_URL']
        self.playwright = None
        self.browser = None
        self.context = None

    async def __aenter__(self):
        """Асинхронный контекстный менеджер для инициализации браузера"""
        await self.init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие браузера"""
        await self.close_browser()

    async def init_browser(self):
        """Инициализация браузера Playwright"""
        try:
            self.playwright = await async_playwright().start()
            
            # Запускаем браузер с параметрами для обхода детекции
            self.browser = await self.playwright.chromium.launch(
                headless=CONFIG['HEADLESS'],
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-extensions',
                    '--disable-plugins',
                    '--disable-web-security',
                    '--disable-features=TranslateUI',
                    '--disable-ipc-flooding-protection',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding'
                ]
            )
            
            # Создаем контекст с дополнительными параметрами
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='Europe/Kiev',
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9,uk;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
            )
            
            # Добавляем скрипт для маскировки автоматизации
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en', 'uk'],
                });
                
                window.chrome = {
                    runtime: {},
                };
                
                Object.defineProperty(navigator, 'permissions', {
                    get: () => ({
                        query: () => Promise.resolve({ state: 'granted' }),
                    }),
                });
            """)
            
            logger.info("Браузер Playwright успешно инициализирован")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации браузера: {e}")
            raise

    async def close_browser(self):
        """Закрытие браузера и освобождение ресурсов"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Браузер закрыт")
        except Exception as e:
            logger.error(f"Ошибка при закрытии браузера: {e}")

    async def get_page_content(self, url: str, max_retries: int = 3):
        """Получает содержимое страницы через Playwright"""
        for attempt in range(max_retries):
            page = None
            try:
                logger.info(f"Попытка загрузки {url}, попытка {attempt + 1}/{max_retries}")
                
                page = await self.context.new_page()
                
                # Устанавливаем таймауты
                page.set_default_timeout(CONFIG['PAGE_TIMEOUT'])
                page.set_default_navigation_timeout(CONFIG['NAVIGATION_TIMEOUT'])
                
                # Добавляем случайную задержку
                if attempt > 0:
                    delay = random.uniform(3, 8)
                    logger.info(f"Ожидание {delay:.1f} секунд...")
                    await asyncio.sleep(delay)
                
                # Переходим на страницу
                response = await page.goto(url, wait_until='domcontentloaded')
                
                if response:
                    logger.info(f"Статус ответа: {response.status}")
                    
                    if response.status == 200:
                        # Ждем загрузки основного контента
                        try:
                            await page.wait_for_selector('body', timeout=10000)
                            # Дополнительное ожидание для динамического контента
                            await asyncio.sleep(random.uniform(2, 4))
                        except PlaywrightTimeoutError:
                            logger.warning("Таймаут ожидания селектора, продолжаем...")
                        
                        # Получаем HTML
                        html_content = await page.content()
                        logger.info(f"Успешно загружено: {url} ({len(html_content)} символов)")
                        
                        # Импортируем BeautifulSoup здесь для обработки HTML
                        from bs4 import BeautifulSoup
                        return BeautifulSoup(html_content, "html.parser")
                    
                    elif response.status == 403:
                        logger.error(f"Ошибка 403: Доступ запрещен для {url}")
                    elif response.status == 406:
                        logger.error(f"Ошибка 406: Неприемлемый запрос для {url}")
                    else:
                        logger.error(f"HTTP ошибка {response.status} для {url}")
                
                else:
                    logger.error(f"Нет ответа от сервера для {url}")
                
            except PlaywrightTimeoutError as e:
                logger.error(f"Таймаут при загрузке {url}: {e}")
                
            except Exception as e:
                logger.error(f"Ошибка при загрузке {url}: {e}")
                
            finally:
                if page:
                    await page.close()
            
            # Если не последняя попытка, ждем перед повтором
            if attempt < max_retries - 1:
                await asyncio.sleep(random.uniform(5, 10))
        
        logger.error(f"Не удалось загрузить {url} после {max_retries} попыток")
        return None

    def find_latest_news_section(self, soup):
        """Находит блок 'Latest News' на BeSoccer."""
        header_texts = ["Latest News", "latest news", "News", "news"]
        for header_text in header_texts:
            header_element = soup.find(text=re.compile(header_text, re.I))
            if header_element:
                logger.info(f"Найден заголовок: '{header_text}'")
                parent = header_element.parent
                while parent and parent.name not in ['section', 'div', 'article']:
                    parent = parent.parent
                if parent:
                    news_container = parent.find_next(['div', 'ul', 'section'])
                    return news_container or parent

        possible_selectors = [
            '.news-list', '.latest-news', '.news-feed', '.content-item',
            '[class*="news"]', '[class*="latest"]', '.news-container'
        ]
        for selector in possible_selectors:
            elements = soup.select(selector)
            for element in elements:
                links = element.find_all('a', href=True)
                soccer_links = [link for link in links if self.is_soccer_news_link(link.get('href', ''))]
                if len(soccer_links) >= 3:
                    logger.info(f"Найден блок новостей через селектор: {selector}")
                    return element

        logger.warning("Ищем новости в основном контенте...")
        main_content_selectors = ['main', '.main-content', '.page-content', 'body']
        for selector in main_content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                all_links = main_content.find_all('a', href=True)
                soccer_links = [link for link in all_links if self.is_soccer_news_link(link.get('href', '')) and len(link.get_text(strip=True)) > 10]
                if len(soccer_links) >= 5:
                    logger.info(f"Найдено {len(soccer_links)} новостей в {selector}")
                    virtual_container = soup.new_tag('div')
                    for link in soccer_links[:10]:
                        virtual_container.append(link.parent or link)
                    return virtual_container

        logger.error("Блок с новостями не найден")
        return None

    def is_soccer_news_link(self, href):
        """Проверяет, является ли ссылка футбольной новостью."""
        if not href:
            return False
        if any(re.search(pattern, href, re.I) for pattern in CONFIG['EXCLUDE_PATTERNS']):
            return False
        return any(re.search(pattern, href, re.I) for pattern in CONFIG['SOCCER_PATTERNS'])

    def extract_news_from_section(self, section, since_time: Optional[datetime] = None):
        """Извлекает новости из секции."""
        if not section:
            return []

        news_links = []
        all_links = section.find_all('a', href=True)
        logger.info(f"Найдено {len(all_links)} ссылок в секции")

        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            if self.is_soccer_news_link(href) and len(text) > 15:
                full_url = href if href.startswith('http') else urljoin(self.base_url, href)
                news_links.append({'title': text, 'url': full_url, 'href': href})
                logger.info(f"Найдена новость: {text[:50]}...")

        seen_urls = set()
        unique_news = [news for news in news_links if news['url'] not in seen_urls and not seen_urls.add(news['url'])]
        return unique_news[:CONFIG['MAX_NEWS_ITEMS']] if not since_time else unique_news

    def translate_to_ukrainian(self, text: str, context: str = "футбольна новина") -> str:
        """Переводит текст на украинский с помощью Gemini."""
        if not has_gemini_key() or not gemini_model or not text:
            return text

        clean_text = re.sub(r'\s+', ' ', text).strip()
        if len(clean_text) < 5:
            return text

        prompt = f"""Переклади текст з англійської на українську. Це {context}.
Правила:
- Зберігай футбольну термінологію
- Використовуй природну українську мову
- Зберігай емоційний тон
- Не додавай пояснень
Текст: {clean_text}
Переклад:"""

        try:
            response = gemini_model.generate_content(prompt)
            translated = re.sub(r'^(Переклад:)\s*', '', response.text.strip())
            logger.info(f"Переведено: {clean_text[:30]}... → {translated[:30]}...")
            return translated
        except Exception as e:
            logger.error(f"Ошибка перевода: {e}")
            return text

    def parse_besoccer_date(self, date_text: str) -> Optional[datetime]:
        """Парсит дату BeSoccer."""
        try:
            if not date_text:
                return None
            current_time = datetime.now(KIEV_TZ)
            date_text = date_text.lower().strip()

            if hours_match := re.search(r'(\d+)h\s*ago', date_text):
                return current_time - timedelta(hours=int(hours_match.group(1)))
            if minutes_match := re.search(r'(\d+)m\s*ago', date_text):
                return current_time - timedelta(minutes=int(minutes_match.group(1)))
            if days_match := re.search(r'(\d+)d\s*ago', date_text):
                return current_time - timedelta(days=int(days_match.group(1)))
            if 'yesterday' in date_text:
                return current_time - timedelta(days=1)
            if 'today' in date_text:
                return current_time.replace(hour=12, minute=0, second=0, microsecond=0)
            if match := re.match(r'(\d{1,2})\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*(\d{4})', date_text, re.I):
                month = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}[match.group(2).lower()]
                return datetime(int(match.group(3)), month, int(match.group(1)), tzinfo=KIEV_TZ)
            return None
        except Exception as e:
            logger.error(f"Ошибка парсинга даты '{date_text}': {e}")
            return None

    def estimate_article_publish_time(self, soup, url: str) -> Optional[datetime]:
        """Определяет время публикации статьи."""
        logger.info(f"Определяем время публикации: {url}")
        for selector in CONFIG['TIME_SELECTORS']:
            time_elem = soup.select_one(selector)
            if time_elem:
                datetime_attr = time_elem.get('datetime') or time_elem.get('data-date')
                if datetime_attr:
                    try:
                        parsed_date = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00')).astimezone(KIEV_TZ)
                        logger.info(f"Время из атрибута: {parsed_date}")
                        return parsed_date
                    except Exception as e:
                        logger.error(f"Ошибка парсинга datetime: {e}")
                if time_text := time_elem.get_text(strip=True):
                    if parsed_time := self.parse_besoccer_date(time_text):
                        logger.info(f"Время из текста: {parsed_time}")
                        return parsed_time

        for selector in CONFIG['META_TIME_SELECTORS']:
            meta_tag = soup.select_one(selector)
            if meta_tag and (content := meta_tag.get('content', '')):
                try:
                    parsed_date = datetime.fromisoformat(content.replace('Z', '+00:00')).astimezone(KIEV_TZ)
                    logger.info(f"Время из мета-тега: {parsed_date}")
                    return parsed_date
                except Exception as e:
                    logger.error(f"Ошибка парсинга мета-даты: {e}")

        logger.warning("Не удалось определить время публикации")
        return None

    def extract_article_content(self, soup):
        """Извлекает текст статьи."""
        for selector in CONFIG['CONTENT_SELECTORS']:
            content_elem = soup.select_one(selector)
            if content_elem:
                for unwanted in content_elem.find_all(['script', 'style', 'iframe', 'aside', '[class*="ad"]']):
                    unwanted.decompose()
                paragraphs = content_elem.find_all('p')
                if paragraphs:
                    main_content = '\n'.join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)
                    logger.info(f"Извлечено {len(main_content)} символов")
                    return main_content

        all_paragraphs = [p.get_text(strip=True) for p in soup.find_all('p') 
                         if len(p.get_text(strip=True)) > 30 and not any(skip in p.get_text(strip=True).lower() for skip in ['cookie', 'advertisement', 'subscribe', 'follow us'])]
        main_content = '\n'.join(all_paragraphs[:5])
        logger.info(f"Извлечено {len(main_content)} символов из параграфов")
        return main_content

    def extract_main_image(self, soup, base_url):
        """Извлекает главное изображение статьи с приоритетом на контент."""
        logger.info("Поиск изображения для статьи...")
        
        # Поиск изображения внутри блока контента
        for content_selector in CONFIG['CONTENT_SELECTORS']:
            content_elem = soup.select_one(content_selector)
            if content_elem:
                for img_selector in ['img', '.news-image img', '.article-image img']:
                    img_elem = content_elem.select_one(img_selector)
                    if img_elem:
                        image_url = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-original')
                        if image_url:
                            if image_url.startswith('//'):
                                image_url = 'https:' + image_url
                            elif image_url.startswith('/'):
                                image_url = 'https://www.besoccer.com' + image_url
                            elif not image_url.startswith('http'):
                                image_url = urljoin(base_url, image_url)
                            if not any(keyword in image_url.lower() for keyword in CONFIG['EXCLUDE_IMAGE_KEYWORDS']):
                                logger.info(f"Найдено изображение в контекте: {image_url}")
                                return image_url

        # Поиск по общим селекторам, если в контекте не найдено
        for selector in CONFIG['IMAGE_SELECTORS']:
            img_elem = soup.select_one(selector)
            if img_elem:
                image_url = img_elem.get('content' if 'meta' in selector else 'src') or img_elem.get('data-src') or img_elem.get('data-original')
                if image_url:
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/'):
                        image_url = 'https://www.besoccer.com' + image_url
                    elif not image_url.startswith('http'):
                        image_url = urljoin(base_url, image_url)
                    if not any(keyword in image_url.lower() for keyword in CONFIG['EXCLUDE_IMAGE_KEYWORDS']):
                        logger.info(f"Найдено изображение по селектору {selector}: {image_url}")
                        return image_url

        logger.warning("Изображение не найдено или все кандидаты исключены")
        return ''

    async def get_full_article_data(self, news_item, since_time: Optional[datetime] = None):
        """Получает полные данные статьи с переводом."""
        url = news_item['url']
        
        # Добавляем случайную задержку между запросами
        delay = random.uniform(*CONFIG['REQUEST_DELAY'])
        logger.info(f"Ожидание {delay:.1f} секунд перед запросом...")
        await asyncio.sleep(delay)
        
        soup = await self.get_page_content(url)
        if not soup:
            return None

        try:
            publish_time = self.estimate_article_publish_time(soup, url)
            if since_time and publish_time and publish_time <= since_time:
                logger.info(f"Старая статья ({publish_time.strftime('%H:%M %d.%m')}) - пропускаем")
                return None
            elif since_time:
                logger.info("Статья новая или время неизвестно")

            original_content = self.extract_article_content(soup)
            original_title = news_item['title']
            translated_title = self.translate_to_ukrainian(original_title, "заголовок футбольної новини")
            translated_content = self.translate_to_ukrainian(original_content, "текст футбольної новини")
            summary = self.create_ukrainian_summary(translated_content, translated_title)
            image_url = self.extract_main_image(soup, url)

            return {
                'title': translated_title,
                'original_title': original_title,
                'url': url,
                'content': translated_content,
                'original_content': original_content,
                'summary': summary,
                'image_url': image_url,
                'publish_time': publish_time,
                'source': 'BeSoccer'
            }
        except Exception as e:
            logger.error(f"Ошибка обработки {url}: {e}")
            return None

    def create_ukrainian_summary(self, content, title):
        """Создает краткую выжимку на украинском."""
        if not content:
            return title
        sentences = re.split(r'[.!?]+', content)
        meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 20][:2]
        summary = '. '.join(meaningful_sentences) + ('.' if meaningful_sentences and not meaningful_sentences[-1].endswith('.') else '')
        return summary or (content[:200] + '...' if len(content) > 200 else content)

    async def get_latest_news(self, since_time: Optional[datetime] = None):
        """Получает новости BeSoccer с переводом."""
        logger.info(f"Загружаем страницу BeSoccer... {'с ' + since_time.strftime('%H:%M %d.%m.%Y') if since_time else ''}")
        soup = await self.get_page_content(self.base_url)
        if not soup:
            logger.error("Не удалось загрузить страницу")
            return []

        headlines_section = self.find_latest_news_section(soup)
        if not headlines_section:
            logger.error("Блок 'Latest News' не найден")
            return []

        news_items = self.extract_news_from_section(headlines_section, since_time)
        if not news_items:
            logger.error("Новости не найдены")
            return []

        logger.info(f"Найдено {len(news_items)} новостей")
        full_articles = []
        for i, news_item in enumerate(news_items, 1):
            logger.info(f"Обрабатываем новость {i}/{len(news_items)}: {news_item['title'][:50]}...")
            article_data = await self.get_full_article_data(news_item, since_time)
            if since_time and article_data is None:
                logger.info("Обнаружена старая новость, прекращаем обработку")
                break
            if article_data:
                full_articles.append(article_data)

        logger.info(f"Обработано {len(full_articles)} новых статей")
        return full_articles

async def get_besoccer_news(since_time: Optional[datetime] = None):
    """Функция для получения новостей BeSoccer с использованием Playwright."""
    async with BeSoccerPlaywrightParser() as parser:
        articles = await parser.get_latest_news(since_time)
        return [
            {
                'title': article['title'],
                'link': article['url'],
                'url': article['url'],
                'summary': article['summary'],
                'image_url': article['image_url'],
                'content': article['content'],
                'publish_time': article.get('publish_time'),
                'source': 'BeSoccer',
                'original_title': article.get('original_title', ''),
                'original_content': article.get('original_content', '')
            }
            for article in articles
        ]

async def test_besoccer_parser_async():
    """Тестирование парсера BeSoccer с Playwright."""
    logger.info("ТЕСТИРУЕМ BESOCCER PARSER С PLAYWRIGHT")
    logger.info("=" * 60)
    
    try:
        async with BeSoccerPlaywrightParser() as parser:
            articles = await parser.get_latest_news()
            
            if articles:
                logger.info(f"Найдено {len(articles)} новостей")
                for i, article in enumerate(articles, 1):
                    time_str = article.get('publish_time').strftime('%H:%M %d.%m') if article.get('publish_time') else 'неизвестно'
                    logger.info(f"{i}. {article['title'][:60]}... ({time_str})")
                    logger.info(f"   Оригинал: {article.get('original_title', '')[:60]}...")
                    logger.info(f"   Изображение: {'✅ ' + article['image_url'][:50] + '...' if article.get('image_url') else '❌'}")
            
            if articles:
                logger.info("Тест качества перевода")
                test_article = articles[0]
                logger.info(f"Оригинальный заголовок: {test_article.get('original_title', '')}")
                logger.info(f"Переведенный заголовок: {test_article['title']}")
                logger.info(f"Оригинальный текст: {test_article.get('original_content', '')[:200]}...")
                logger.info(f"Переведенный текст: {test_article.get('content', '')[:200]}...")
            return articles
            
    except Exception as e:
        logger.error(f"Ошибка тестирования: {e}")
        return []

def test_besoccer_parser():
    """Синхронная обертка для тестирования."""
    return asyncio.run(test_besoccer_parser_async())

if __name__ == "__main__":
    test_besoccer_parser()
