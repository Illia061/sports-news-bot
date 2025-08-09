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
    'NEWS_API_URL': 'https://onefootball.com/en/news',  # Альтернативный URL для новостей
    'MAX_NEWS': 10,
    'RETRY_ATTEMPTS': 3,
    'RETRY_DELAY': 2
}

KIEV_TZ = ZoneInfo("Europe/Kiev")

class OneFootballParser:
    def __init__(self):
        self.base_url = CONFIG['BASE_URL']
        self.news_url = CONFIG['NEWS_API_URL']
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(CONFIG['USER_AGENTS']),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,uk;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Referer": "https://onefootball.com/",
        })
        

    def parse_publish_time(self, time_str: str, current_time: datetime = None) -> datetime:
        """Преобразует строку времени в объект datetime с киевским часовым поясом (EEST)."""
        try:
            if not current_time:
                current_time = datetime.now(KIEV_TZ)
            logger.debug(f"Попытка парсинга времени: {time_str}, текущее время: {current_time}")

            if 'ago' in time_str.lower():
                # Парсим относительное время (например, "2 hours ago", "30 minutes ago")
                numbers = re.findall(r'\d+', time_str)
                if numbers:
                    value = int(numbers[0])
                    if 'second' in time_str.lower():
                        delta = timedelta(seconds=value)
                    elif 'minute' in time_str.lower():
                        delta = timedelta(minutes=value)
                    elif 'hour' in time_str.lower():
                        delta = timedelta(hours=value)
                    elif 'day' in time_str.lower():
                        delta = timedelta(days=value)
                    else:
                        # По умолчанию считаем минуты
                        delta = timedelta(minutes=value)
                    return current_time - delta
                else:
                    return current_time - timedelta(minutes=5)  # Дефолт для неопознанного "ago"

            # Парсим ISO формат
            if 'T' in time_str:
                dt = datetime.fromisoformat(time_str.replace('Z', '+00:00')).astimezone(KIEV_TZ)
                logger.debug(f"Успешно распарсено ISO время: {time_str} -> {dt}")
                return dt
            
            # Пытаемся парсить различные форматы даты
            date_formats = [
                '%Y-%m-%d %H:%M %Z',
                '%Y-%m-%d %H:%M',
                '%Y-%m-%dT%H:%M:%S',
                '%d.%m.%Y %H:%M',
                '%d/%m/%Y %H:%M'
            ]
            
            for fmt in date_formats:
                try:
                    dt = datetime.strptime(time_str, fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=KIEV_TZ)
                    else:
                        dt = dt.astimezone(KIEV_TZ)
                    logger.debug(f"Успешно распарсено время: {time_str} -> {dt}")
                    return dt
                except ValueError:
                    continue
            
            logger.warning(f"Не удалось распарсить время '{time_str}', используем текущее")
            return current_time
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга времени '{time_str}': {e}")
            return current_time

    def get_page_content(self, url: str, attempt: int = 1) -> BeautifulSoup:
        """Получает содержимое страницы с повторными попытками."""
        try:
            logger.info(f"🌐 Загружаем страницу (попытка {attempt}/{CONFIG['RETRY_ATTEMPTS']}): {url}")
            
            # Меняем User-Agent для каждой попытки
            self.session.headers.update({
                "User-Agent": random.choice(CONFIG['USER_AGENTS'])
            })
            
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            
            logger.info(f"✅ Страница загружена: {len(response.content)} байт")
            
            # Сохраняем HTML для отладки
            debug_filename = f'onefootball_debug_{attempt}.html'
            with open(debug_filename, 'w', encoding='utf-8') as f:
                f.write(response.text)
            logger.info(f"🔍 HTML сохранен для отладки: {debug_filename}")
            
            return BeautifulSoup(response.text, "html.parser")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Ошибка сетевого запроса (попытка {attempt}): {e}")
            if attempt < CONFIG['RETRY_ATTEMPTS']:
                logger.info(f"⏳ Ждем {CONFIG['RETRY_DELAY']} секунд перед следующей попыткой...")
                time.sleep(CONFIG['RETRY_DELAY'])
                return self.get_page_content(url, attempt + 1)
            return None
        except Exception as e:
            logger.error(f"❌ Общая ошибка загрузки (попытка {attempt}): {e}")
            if attempt < CONFIG['RETRY_ATTEMPTS']:
                time.sleep(CONFIG['RETRY_DELAY'])
                return self.get_page_content(url, attempt + 1)
            return None

    def debug_page_structure(self, soup: BeautifulSoup):
        """Отладочная функция для анализа структуры страницы."""
        logger.info("🔍 АНАЛИЗ СТРУКТУРЫ СТРАНИЦЫ:")
        logger.info("=" * 50)
        
        # Анализ всех div'ов с классами
        all_divs = soup.find_all('div', class_=True)[:20]  # Первые 20
        logger.info(f"📦 Найдено {len(all_divs)} div элементов с классами (показываем первые 20):")
        for i, div in enumerate(all_divs, 1):
            classes = ' '.join(div.get('class', []))
            logger.info(f"   {i:2d}. div class=\"{classes}\"")
        
        # Анализ article элементов
        articles = soup.find_all('article')
        logger.info(f"📰 Найдено {len(articles)} article элементов")
        for i, article in enumerate(articles[:5], 1):
            classes = ' '.join(article.get('class', []))
            logger.info(f"   {i}. article class=\"{classes}\"")
        
        # Анализ ссылок на новости
        links = soup.find_all('a', href=True)
        news_links = [link for link in links if any(word in link['href'] for word in ['/news/', '/match/', '/article/'])][:10]
        logger.info(f"🔗 Найдено {len(news_links)} ссылок на новости (показываем первые 10):")
        for i, link in enumerate(news_links, 1):
            href = link['href']
            text = link.get_text(strip=True)[:50]
            logger.info(f"   {i:2d}. {href} -> \"{text}...\"")
        
        # Анализ заголовков
        headers = soup.find_all(['h1', 'h2', 'h3', 'h4'])[:10]
        logger.info(f"🏷️  Найдено {len(headers)} заголовков (показываем первые 10):")
        for i, header in enumerate(headers, 1):
            text = header.get_text(strip=True)
            classes = ' '.join(header.get('class', []))
            logger.info(f"   {i:2d}. {header.name} \"{text[:50]}...\" class=\"{classes}\"")
        
        # Поиск JSON-LD данных
        json_scripts = soup.find_all('script', type='application/ld+json')
        logger.info(f"🔧 Найдено {len(json_scripts)} JSON-LD скриптов")
        
        logger.info("=" * 50)

    def extract_news_from_scripts(self, soup: BeautifulSoup) -> list:
        """Пытается извлечь новости из JSON-LD или других скриптов."""
        try:
            # Поиск JSON-LD данных
            json_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    logger.info(f"📊 Найден JSON-LD: {type(data)}")
                    # Здесь можно добавить логику парсинга JSON-LD
                except:
                    continue
            
            # Поиск обычных скриптов с данными
            all_scripts = soup.find_all('script')
            for script in all_scripts:
                script_content = script.string or ""
                if 'window.__INITIAL_STATE__' in script_content or 'window.__DATA__' in script_content:
                    logger.info("📊 Найден скрипт с начальными данными")
                    # Здесь можно добавить извлечение данных из JavaScript
                    
        except Exception as e:
            logger.error(f"Ошибка при извлечении данных из скриптов: {e}")
        
        return []

    def find_news_articles_advanced(self, soup: BeautifulSoup) -> list:
        """Расширенный поиск статей на странице."""
        found_articles = []
        
        # Метод 1: Поиск по ссылкам на новости
        logger.info("🔍 Метод 1: Поиск по ссылкам на новости")
        news_links = soup.find_all('a', href=True)
        for link in news_links:
            href = link.get('href', '')
            if any(pattern in href for pattern in ['/news/', '/match/', '/article/', '/story/']):
                title_text = link.get_text(strip=True)
                if title_text and len(title_text) > 10:
                    # Пытаемся найти родительский контейнер
                    parent_article = link.find_parent(['article', 'div', 'li'])
                    if parent_article:
                        found_articles.append({
                            'element': parent_article,
                            'link': link,
                            'title': title_text,
                            'url': href,
                            'method': 'link_based'
                        })
        
        logger.info(f"   Найдено {len(found_articles)} статей через ссылки")
        
        # Метод 2: Поиск по заголовкам
        logger.info("🔍 Метод 2: Поиск по заголовкам")
        headers = soup.find_all(['h1', 'h2', 'h3', 'h4'])
        for header in headers:
            title_text = header.get_text(strip=True)
            if title_text and len(title_text) > 15:  # Минимальная длина заголовка
                # Ищем ссылку рядом с заголовком
                parent = header.find_parent(['article', 'div', 'li', 'section'])
                if parent:
                    link = parent.find('a', href=True)
                    if link and any(pattern in link.get('href', '') for pattern in ['/news/', '/match/', '/article/', '/story/']):
                        # Проверяем, не добавили ли мы уже эту статью
                        if not any(art['url'] == link['href'] for art in found_articles):
                            found_articles.append({
                                'element': parent,
                                'link': link,
                                'title': title_text,
                                'url': link['href'],
                                'method': 'header_based'
                            })
        
        logger.info(f"   Найдено {len(found_articles)} уникальных статей всего")
        
        # Метод 3: Структурный поиск
        logger.info("🔍 Метод 3: Структурный поиск")
        structural_selectors = [
            '[data-testid*="article"]',
            '[data-testid*="story"]',
            '[data-testid*="news"]',
            '[class*="article"]',
            '[class*="story"]',
            '[class*="news-item"]',
            '[class*="card"]'
        ]
        
        for selector in structural_selectors:
            elements = soup.select(selector)
            for element in elements:
                link = element.find('a', href=True)
                title_elem = element.find(['h1', 'h2', 'h3', 'h4'])
                
                if link and title_elem:
                    href = link.get('href', '')
                    title_text = title_elem.get_text(strip=True)
                    
                    if (title_text and len(title_text) > 10 and 
                        any(pattern in href for pattern in ['/news/', '/match/', '/article/', '/story/']) and
                        not any(art['url'] == href for art in found_articles)):
                        
                        found_articles.append({
                            'element': element,
                            'link': link,
                            'title': title_text,
                            'url': href,
                            'method': f'structural_{selector}'
                        })
        
        logger.info(f"   Итого найдено {len(found_articles)} уникальных статей")
        
        # Удаляем дубликаты по URL
        unique_articles = []
        seen_urls = set()
        for article in found_articles:
            if article['url'] not in seen_urls:
                unique_articles.append(article)
                seen_urls.add(article['url'])
        
        logger.info(f"✅ Финальный результат: {len(unique_articles)} уникальных статей")
        return unique_articles

    def extract_article_data(self, article_data: dict, current_time: datetime) -> dict:
        """Извлекает все необходимые данные из найденной статьи."""
        try:
            element = article_data['element']
            link = article_data['link']
            
            # Основные данные
            url = link.get('href', '')
            if not url.startswith('http'):
                url = urljoin(self.base_url, url)
            
            title = article_data['title']
            
            # Ищем время публикации
            time_elem = element.find('time')
            if not time_elem:
                time_elem = element.find(attrs={'datetime': True})
            if not time_elem:
                time_elem = element.find(text=re.compile(r'\d+\s*(hour|minute|day)s?\s*ago', re.I))
            
            time_str = ""
            if time_elem:
                if hasattr(time_elem, 'get'):
                    time_str = time_elem.get('datetime', '') or time_elem.get_text(strip=True)
                else:
                    time_str = str(time_elem).strip()
            
            publish_time = self.parse_publish_time(time_str, current_time) if time_str else current_time
            
            # Ищем изображение
            img_elem = element.find('img')
            image_url = ""
            if img_elem:
                image_url = img_elem.get('src', '') or img_elem.get('data-src', '') or img_elem.get('data-lazy-src', '')
                if image_url and not image_url.startswith('http'):
                    image_url = urljoin(self.base_url, image_url)
            
            # Ищем краткое описание
            summary_elem = element.find(['p', 'span', 'div'], class_=re.compile(r'description|summary|excerpt', re.I))
            summary = summary_elem.get_text(strip=True) if summary_elem else ""
            
            result = {
                'title': title,
                'url': url,
                'summary': summary,
                'publish_time': publish_time,
                'image_url': image_url,
                'method': article_data['method'],
                'time_str': time_str
            }
            
            logger.info(f"📰 Извлечена статья ({article_data['method']}): {title[:50]}...")
            logger.info(f"   🔗 URL: {url}")
            logger.info(f"   ⏰ Время: {time_str} -> {publish_time.strftime('%H:%M %d.%m')}")
            if image_url:
                logger.info(f"   🖼️  Изображение: {image_url[:50]}...")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка извлечения данных статьи: {e}")
            return None

    def fetch_full_article(self, url: str) -> tuple[str, str]:
        """Извлекает полный текст и изображение из статьи."""
        try:
            logger.info(f"📄 Загружаем полный текст статьи: {url[:50]}...")
            
            soup = self.get_page_content(url)
            if not soup:
                return "", ""

            # Расширенные селекторы для контента
            content_selectors = [
                '[data-testid*="article-body"]',
                '[data-testid*="story-body"]',
                '.article-content',
                '.story-content',
                '.post-content',
                '[class*="body"]',
                'article',
                '.main-text',
                '.content',
                '[role="main"] p'
            ]

            article_text = ""
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    # Удаляем нежелательные элементы
                    for unwanted in content_div.find_all(['script', 'style', 'iframe', 'nav', 'aside', 'footer']):
                        unwanted.decompose()
                    
                    paragraphs = content_div.find_all('p')
                    if paragraphs:
                        meaningful_paragraphs = []
                        for p in paragraphs:
                            text = p.get_text(strip=True)
                            # Фильтруем короткие и служебные параграфы
                            if (len(text) > 20 and 
                                not any(skip in text.lower() for skip in 
                                       ['cookie', 'advertisement', 'subscribe', 'photo:', 'source:', 'getty images'])):
                                meaningful_paragraphs.append(text)
                        
                        if meaningful_paragraphs:
                            article_text = '\n'.join(meaningful_paragraphs)
                            logger.info(f"   ✅ Извлечен контент через {selector}: {len(article_text)} символов")
                            break
                    else:
                        article_text = content_div.get_text(strip=True)
                        if len(article_text) > 100:  # Минимальная длина
                            logger.info(f"   ✅ Извлечен контент через {selector}: {len(article_text)} символов")
                            break

            # Если основные селекторы не сработали, пробуем общий поиск параграфов
            if not article_text:
                logger.info("   🔄 Основные селекторы не сработали, пробуем общий поиск...")
                all_paragraphs = soup.find_all('p')
                meaningful_paragraphs = []
                for p in all_paragraphs:
                    text = p.get_text(strip=True)
                    if (len(text) > 30 and
                        not any(skip in text.lower() for skip in 
                               ['cookie', 'advertisement', 'subscribe', 'photo', 'source', 'menu', 'navigation'])):
                        meaningful_paragraphs.append(text)
                
                if meaningful_paragraphs:
                    article_text = '\n'.join(meaningful_paragraphs)
                    # Обрезаем если слишком длинный
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
                    logger.info(f"   ✅ Извлечен контент общим поиском: {len(article_text)} символов")

            # Поиск изображения статьи
            image_selectors = [
                'meta[property="og:image"]',
                'meta[name="twitter:image"]',
                '[data-testid*="hero-image"] img',
                '.article-image img',
                '.story-image img',
                '.main-image img',
                '.featured-image img',
                'article img:first-of-type'
            ]

            image_url = ""
            for selector in image_selectors:
                img_elem = soup.select_one(selector)
                if img_elem:
                    if img_elem.name == 'meta':
                        image_url = img_elem.get('content', '')
                    else:
                        image_url = (img_elem.get('src', '') or 
                                   img_elem.get('data-src', '') or 
                                   img_elem.get('data-lazy-src', ''))
                    
                    if image_url:
                        image_url = urljoin(url, image_url)
                        # Проверяем, что это не иконка или логотип
                        if not any(small in image_url.lower() for small in 
                                 ['icon', 'logo', 'thumb', 'avatar', 'placeholder']):
                            logger.info(f"   🖼️  Найдено изображение через {selector}")
                            break
            
            return article_text, image_url

        except Exception as e:
            logger.error(f"Ошибка загрузки статьи {url}: {e}")
            return "", ""



    def get_latest_news(self, since_time: datetime = None) -> list:
        """Получает последние новости с OneFootball с улучшенной логикой поиска."""
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

        logger.info(f"🔍 Загружаем OneFootball (с {since_time.strftime('%H:%M %d.%m.%Y')})...")

        # Пробуем разные URL
        urls_to_try = [
            self.base_url,
            self.news_url,
            'https://onefootball.com/en/news/all',
            'https://onefootball.com/en/competition/1/news'  # Premier League news
        ]
        
        soup = None
        successful_url = None
        
        for url in urls_to_try:
            logger.info(f"🌐 Пробуем загрузить: {url}")
            soup = self.get_page_content(url)
            if soup:
                successful_url = url
                logger.info(f"✅ Успешно загружен: {url}")
                break
            else:
                logger.warning(f"❌ Не удалось загрузить: {url}")
                time.sleep(1)  # Небольшая пауза между попытками
        
        if not soup:
            logger.error("❌ Не удалось загрузить ни один из URL")
            return []

        # Отладка структуры страницы
        self.debug_page_structure(soup)
        
        # Извлечение данных из скриптов (если доступно)
        self.extract_news_from_scripts(soup)
        
        # Расширенный поиск статей
        found_articles = self.find_news_articles_advanced(soup)
        
        if not found_articles:
            logger.error("❌ Не найдено ни одной статьи после всех методов поиска")
            return []
        
        logger.info(f"🔍 Обрабатываем {len(found_articles)} найденных статей...")
        
        news_items = []
        processed_count = 0
        
        # Ограничиваем количество статей для обработки
        articles_to_process = found_articles[:CONFIG['MAX_NEWS']]
        
        for i, article_data in enumerate(articles_to_process, 1):
            try:
                logger.info(f"📰 Обрабатываем статью {i}/{len(articles_to_process)}...")
                
                # Извлекаем базовые данные
                article_info = self.extract_article_data(article_data, current_time)
                if not article_info:
                    continue
                
                # Проверяем время публикации
                if article_info['publish_time'] < since_time:
                    logger.info(f"   ⏰ Статья старая, пропускаем (время: {article_info['publish_time'].strftime('%H:%M %d.%m')})")
                    continue
                
                # Загружаем полный контент статьи
                logger.info(f"   📄 Загружаем полный контент...")
                article_text, full_image_url = self.fetch_full_article(article_info['url'])
                
                # Используем изображение из полной статьи, если оно лучше
                final_image_url = full_image_url or article_info['image_url']
                
                # Формируем итоговый объект новости (БЕЗ перевода - это делает ai_processor)
                news_item = {
                    'title': article_info['title'],  # Оригинальный английский заголовок
                    'url': article_info['url'],
                    'content': article_text,  # Оригинальный английский контент
                    'summary': article_info['summary'],  # Краткое описание
                    'publish_time': article_info['publish_time'],
                    'image_url': final_image_url,
                    'source': 'OneFootball',
                    'extraction_method': article_info['method']
                }
                
                news_items.append(news_item)
                processed_count += 1
                
                logger.info(f"   ✅ Статья добавлена: {article_info['title'][:50]}...")
                
                # Пауза между запросами к статьям
                if i < len(articles_to_process):
                    time.sleep(1)

            except Exception as e:
                logger.error(f"   ❌ Ошибка обработки статьи {i}: {e}")
                continue

        logger.info(f"✅ OneFootball: найдено {processed_count} из {len(found_articles)} статей")
        logger.info("   🔄 Обработка и перевод будут выполнены в ai_processor.py")
        
        # Сортируем по времени публикации (новые сначала)
        news_items.sort(key=lambda x: x.get('publish_time') or datetime.min.replace(tzinfo=KIEV_TZ), reverse=True)
        
        # Показываем финальную статистику
        if news_items:
            logger.info("📊 СПИСОК НАЙДЕННЫХ НОВОСТЕЙ (сырые данные):")
            for i, item in enumerate(news_items, 1):
                publish_time = item.get('publish_time')
                time_str = publish_time.strftime('%H:%M %d.%m') if publish_time else 'неизвестно'
                method = item.get('extraction_method', 'unknown')
                logger.info(f"   {i:2d}. [{method}] {item['title'][:50]}... ({time_str})")
        
        return news_items


def get_latest_news(since_time: datetime = None) -> list:
    """Функция-обертка для совместимости с main.py."""
    parser = OneFootballParser()
    return parser.get_latest_news(since_time)


if __name__ == "__main__":
    logger.info("🎯 ТЕСТИРУЕМ УЛУЧШЕННЫЙ ПАРСЕР ДЛЯ ONEFOOTBALL")
    logger.info("=" * 60)
    
    # Тестируем без ограничения по времени для отладки
    test_time = datetime.now(KIEV_TZ) - timedelta(hours=24)  # Последние 24 часа
    
    articles = get_latest_news(since_time=test_time)
    
    if articles:
        logger.info(f"✅ УСПЕШНО! Найдено {len(articles)} новостей")
        logger.info("🏆 ИТОГОВАЯ СТАТИСТИКА:")
        
        methods_count = {}
        for article in articles:
            method = article.get('extraction_method', 'unknown')
            methods_count[method] = methods_count.get(method, 0) + 1
        
        logger.info("📈 По методам извлечения:")
        for method, count in methods_count.items():
            logger.info(f"   {method}: {count} статей")
        
        logger.info("\n📰 СПИСОК НОВОСТЕЙ (сырые данные для ai_processor):")
        for i, article in enumerate(articles, 1):
            publish_time = article.get('publish_time')
            time_str = publish_time.strftime('%H:%M %d.%m') if publish_time else 'неизвестно'
            logger.info(f"   {i:2d}. {article['title'][:60]}... ({time_str})")
            if article.get('image_url'):
                logger.info(f"       🖼️  {article['image_url'][:60]}...")
            logger.info(f"       📄 Контент: {len(article.get('content', ''))} символов")
    else:
        logger.error("❌ ОШИБКА! Новостей не найдено")
        logger.info("\n🔧 РЕКОМЕНДАЦИИ ПО ОТЛАДКЕ:")
        logger.info("1. Проверьте файлы onefootball_debug_*.html")
        logger.info("2. Убедитесь, что сайт доступен")
        logger.info("3. Возможно, структура сайта изменилась")
    
    logger.info("=" * 60)
