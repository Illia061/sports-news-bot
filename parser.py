import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo

KIEV_TZ = ZoneInfo("Europe/Kiev")

class FootballUATargetedParser:
    def __init__(self, max_consecutive_old=2):
        self.base_url = "https://football.ua/"
        self.max_consecutive_old = max_consecutive_old
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        })
    
    def get_page_content(self, url):
        """Получает содержимое страницы"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"Ошибка загрузки {url}: {e}")
            return None
    
    def find_golovne_za_dobu_section(self, soup):
        """Находит конкретно блок 'ГОЛОВНЕ ЗА ДОБУ'"""
        header_texts = [
            "ГОЛОВНЕ ЗА ДОБУ",
            "головне за добу", 
            "Головне за добу"
        ]
        
        for header_text in header_texts:
            header_element = soup.find(text=re.compile(header_text, re.I))
            if header_element:
                print(f"✅ Найден заголовок: '{header_text}'")
                parent = header_element.parent
                while parent and parent.name not in ['section', 'div', 'article']:
                    parent = parent.parent
                if parent:
                    news_container = parent.find_next(['div', 'ul', 'section'])
                    if news_container:
                        print(f"✅ Найден контейнер новостей после заголовка")
                        return news_container
                    else:
                        return parent
        
        possible_selectors = [
            '.sidebar', '.right-column', '.side-block', '.news-sidebar',
            '.daily-news', '.main-today', '.today-block', '.golovne',
            '[class*="today"]', '[class*="daily"]', '[class*="golovne"]'
        ]
        
        for selector in possible_selectors:
            elements = soup.select(selector)
            for element in elements:
                if re.search(r'головне.*за.*добу', element.get_text(), re.I):
                    print(f"✅ Найден блок через селектор: {selector}")
                    return element
        
        print("⚠️ Ищем блок через анализ структуры...")
        all_divs = soup.find_all(['div', 'section'], class_=True)
        for div in all_divs:
            div_text = div.get_text().lower()
            if 'головне' in div_text and 'добу' in div_text:
                print(f"✅ Найден блок с текстом 'головне за добу'")
                return div
        
        print("❌ Блок 'ГОЛОВНЕ ЗА ДОБУ' не найден")
        return None
    
    def extract_news_from_section(self, section, since_time: Optional[datetime] = None):
        """Извлекает новости из найденной секции с фильтрацией по времени"""
        if not section:
            return []
        
        news_links = []
        all_links = section.find_all('a', href=True)
        print(f"🔍 Найдено {len(all_links)} ссылок в секции")
        
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            if self.is_news_link(href) and len(text) > 10:
                full_url = urljoin(self.base_url, href)
                news_links.append({
                    'title': text,
                    'url': full_url,
                    'href': href
                })
                print(f"📰 Найдена новость: {text[:50]}...")
        
        seen_urls = set()
        unique_news = []
        for news in news_links:
            if news['url'] not in seen_urls:
                unique_news.append(news)
                seen_urls.add(news['url'])
        
        if since_time:
            print(f"🕒 Фильтруем новости с {since_time.strftime('%H:%M %d.%m.%Y')}")
            return unique_news
        else:
            return unique_news[:5]
    
    def is_news_link(self, href):
        """Проверяет, является ли ссылка новостной"""
        if not href:
            return False
        news_patterns = [
            r'/news/', r'/ukraine/', r'/world/', r'/europe/', r'/england/',
            r'/spain/', r'/italy/', r'/germany/', r'/france/', r'/poland/',
            r'/\d+[^/]*\.html'
        ]
        return any(re.search(pattern, href) for pattern in news_patterns)
    
    def parse_ukrainian_date(self, date_text: str) -> Optional[datetime]:
        """Парсит украинский формат даты"""
        try:
            ukrainian_months = {
                'січня': 1, 'лютого': 2, 'березня': 3, 'квітня': 4, 'травня': 5, 'червня': 6,
                'липня': 7, 'серпня': 8, 'вересня': 9, 'жовтня': 10, 'листопада': 11, 'грудня': 12,
                'січ': 1, 'лют': 2, 'бер': 3, 'кві': 4, 'тра': 5, 'чер': 6,
                'лип': 7, 'сер': 8, 'вер': 9, 'жов': 10, 'лис': 11, 'гру': 12
            }
            cleaned_text = re.sub(r'[,.]', '', date_text.lower().strip())
            pattern1 = r'(\d{1,2})\s+(\w+)\s+(\d{4})[\s,]+(\d{1,2}):(\d{2})'
            match1 = re.search(pattern1, cleaned_text)
            if match1:
                day = int(match1.group(1))
                month_name = match1.group(2)
                year = int(match1.group(3))
                hour = int(match1.group(4))
                minute = int(match1.group(5))
                if month_name in ukrainian_months:
                    month = ukrainian_months[month_name]
                    return datetime(year, month, day, hour, minute, tzinfo=KIEV_TZ)
            pattern2 = r'(\d{1,2})\.(\d{1,2})\.(\d{4})[\s,]+(\d{1,2}):(\d{2})'
            match2 = re.search(pattern2, cleaned_text)
            if match2:
                day = int(match2.group(1))
                month = int(match2.group(2))
                year = int(match2.group(3))
                hour = int(match2.group(4))
                minute = int(match2.group(5))
                return datetime(year, month, day, hour, minute, tzinfo=KIEV_TZ)
            pattern3 = r'^(\d{1,2}):(\d{2})$'
            match3 = re.search(pattern3, cleaned_text)
            if match3:
                hour = int(match3.group(1))
                minute = int(match3.group(2))
                today = datetime.now(KIEV_TZ).replace(hour=hour, minute=minute, second=0, microsecond=0)
                return today
        except Exception as e:
            print(f"⚠️ Ошибка парсинга украинской даты '{date_text}': {e}")
        return None
    
    def estimate_article_publish_time(self, soup, url: str) -> Optional[datetime]:
        """Пытается определить время публикации статьи"""
        try:
            print(f"🕒 Определяем время публикации для: {url}")
            meta_selectors = [
                'meta[property="article:published_time"]',
                'meta[name="publish_date"]', 'meta[name="date"]',
                'meta[property="og:published_time"]',
                'meta[name="DC.date"]', 'meta[itemprop="datePublished"]'
            ]
            for selector in meta_selectors:
                meta_tag = soup.select_one(selector)
                if meta_tag:
                    content = meta_tag.get('content', '')
                    if content:
                        print(f"📅 Найден мета-тег {selector}: {content}")
                        try:
                            if 'T' in content:
                                parsed_date = datetime.fromisoformat(content.replace('Z', '+00:00').replace('+00:00', ''))
                                parsed_date_kiev = parsed_date.astimezone(KIEV_TZ)
                                print(f"✅ Успешно спарсен мета-тег: {parsed_date_kiev}")
                                return parsed_date_kiev
                        except Exception as e:
                            print(f"⚠️ Не удалось спарсить мета-тег: {e}")
                            continue
            date_selectors = [
                '.article-date', '.publish-date', '.news-date',
                '.date', '.timestamp', 'time[datetime]',
                '.article-time', '.post-date', '.entry-date',
                '[class*="date"]', '[class*="time"]'
            ]
            for selector in date_selectors:
                date_elem = soup.select_one(selector)
                if date_elem:
                    datetime_attr = date_elem.get('datetime')
                    if datetime_attr:
                        print(f"📅 Найден datetime атрибут: {datetime_attr}")
                        try:
                            parsed_date = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00').replace('+00:00', ''))
                            parsed_date_kiev = parsed_date.astimezone(KIEV_TZ)
                            print(f"✅ Успешно спарсен datetime: {parsed_date_kiev}")
                            return parsed_date_kiev
                        except Exception as e:
                            print(f"⚠️ Не удалось спарсить datetime: {e}")
                    date_text = date_elem.get_text(strip=True)
                    if date_text:
                        print(f"📅 Найден текст даты в {selector}: '{date_text}'")
                        parsed_date = self.parse_ukrainian_date(date_text)
                        if parsed_date:
                            print(f"✅ Успешно спарсен текст даты: {parsed_date}")
                            return parsed_date
            all_text = soup.get_text()
            date_patterns = [
                r'(\d{1,2})\s+(січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)\s+(\d{4})[\s,]+(\d{1,2}):(\d{2})',
                r'(\d{1,2})\.(\d{1,2})\.(\d{4})[\s,]+(\d{1,2}):(\d{2})',
                r'(\d{1,2})/(\d{1,2})/(\d{4})[\s,]+(\d{1,2}):(\d{2})'
            ]
            for pattern in date_patterns:
                matches = re.findall(pattern, all_text, re.IGNORECASE)
                for match in matches[:3]:
                    if len(match) >= 5:
                        try:
                            if 'січня' in pattern or 'лютого' in pattern:
                                parsed_date = self.parse_ukrainian_date(' '.join(match))
                            else:
                                day, month, year, hour, minute = map(int, match)
                                parsed_date = datetime(year, month, day, hour, minute, tzinfo=KIEV_TZ)
                            if parsed_date:
                                print(f"✅ Найдена дата в тексте: {parsed_date}")
                                return parsed_date
                        except Exception as e:
                            print(f"⚠️ Ошибка парсинга найденной даты: {e}")
                            continue
            print(f"⚠️ Не удалось определить точное время публикации")
            return None
        except Exception as e:
            print(f"⚠️ Ошибка определения времени публикации: {e}")
            return None
    
    def count_words(self, text: str) -> int:
        """ТОЧНЫЙ подсчет слов как делает человек - только значимые слова"""
        if not text:
            return 0
        clean_text = re.sub(r'<[^>]+>', '', text)
        service_patterns = [
            r'\d{1,2}\s+\w+\s+\d{4},\s+\d{1,2}:\d{2}',  # даты и время
            r'getty images', r'фото:.*', r'джерело:.*',
            r'читайте також:.*', r'\([^)]*\)'
        ]
        for pattern in service_patterns:
            clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        word_text = re.sub(r'[^\w\s]', ' ', clean_text, flags=re.UNICODE)
        words = []
        for word in word_text.split():
            word = word.strip()
            if len(word) >= 2 and not word.isdigit():
                words.append(word)
        return len(words)
    
    def extract_clean_article_content(self, soup):
        """Извлечение ТОЛЬКО основного текста статьи без подзаголовков, списков и служебной информации"""
        soup_copy = BeautifulSoup(str(soup), 'html.parser')
        
        # Удаляем ненужные элементы
        unwanted_selectors = [
            'script', 'style', 'iframe', 'noscript', 'svg',
            'header', 'nav', 'footer', 'aside',
            '.header', '.footer', '.navigation', '.nav',
            '[class*="ad"]', '[class*="banner"]', '[class*="advertisement"]',
            '[class*="social"]', '[class*="share"]', '[class*="related"]',
            '[class*="comment"]', '[class*="sidebar"]', '[class*="widget"]',
            '.breadcrumb', '.tags', '.meta', '.author', '.date', '.time',
            '.article-date', '.publish-date', '.news-date',
            '[class*="date"]', '[class*="time"]', '[class*="meta"]',
            '.social-buttons', '.article-info', '.news-info',
            '.photo-credit', '.image-caption', '.getty-images',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',  # Исключаем подзаголовки
            'ul', 'ol', 'li',  # Исключаем списки
            'blockquote',  # Исключаем цитаты
        ]
        for selector in unwanted_selectors:
            for element in soup_copy.select(selector):
                element.decompose()
    
        # Строго выбираем основной контент
        main_selectors = [
            '.article-body p',  # Основной текст статьи
            '.news-content p', 
            '.post-content p',
            '.main-content p',
            '.content p:not(.caption):not([class*="meta"]):not([class*="info"])',  # Исключаем подписи и мета-информацию
            'article p'
        ]
    
        article_paragraphs = []
        for selector in main_selectors:
            paragraphs = soup_copy.select(selector)
            if paragraphs:
                print(f"🎯 Найдены параграфы через селектор: {selector}")
                article_paragraphs = paragraphs
                break
    
        if not article_paragraphs:
            print("⚠️ Используем параграфы внутри article или .content")
            article_container = soup_copy.select_one('article, .content, .article-body, .news-content')
            if article_container:
                article_paragraphs = article_container.find_all('p', recursive=False)
    
        # Фильтруем параграфы, чтобы оставить только содержательные
        meaningful_paragraphs = []
        for p in article_paragraphs:
            p_text = p.get_text(strip=True)
            if (len(p_text) > 30 and  # Увеличиваем минимальную длину для исключения коротких фраз
                not p.find_parent(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'blockquote']) and
                not any(skip_phrase in p_text.lower() for skip_phrase in [
                    'getty images', 'фото:', 'джерело:', 'читайте також',
                    'підписуйтесь', 'стежите', 'telegram', 'facebook', 'twitter',
                    'про це повідомляє', 'football.ua', 'футбол.ua',
                    'cookie', 'реклам', 'коментар', 'автор:', 'теги:'
                ]) and
                not re.match(r'^\d{1,2}\s+\w+\s+\d{4},\s+\d{1,2}:\d{2}$', p_text) and
                not re.match(r'^[А-ЯІЄ][а-яієї]+\s+[А-ЯІЄ][а-яієї]+,\s*getty images$', p_text, re.IGNORECASE)
            ):
                meaningful_paragraphs.append(p_text)
    
        # Объединяем содержательные параграфы
        main_content = ' '.join(meaningful_paragraphs)
        print(f"📄 Извлечено {len(main_content)} символов основного текста")
        print(f"📊 Из {len(meaningful_paragraphs)} содержательных параграфов")
        if main_content:
            print(f"🔍 Первые 200 символов: {main_content[:200]}...")
        return main_content
    
    def get_full_article_data(self, news_item, since_time: Optional[datetime] = None):
        """Получение полных данных статьи с быстрой проверкой времени"""
        url = news_item['url']
        soup = self.get_page_content(url)
        if not soup:
            return None
        try:
            if since_time:
                publish_time = self.estimate_article_publish_time(soup, url)
                if publish_time and publish_time <= since_time:
                    print(f"⏰ Статья опубликована {publish_time.strftime('%H:%M %d.%m')} - старая")
                    return None
            else:
                publish_time = self.estimate_article_publish_time(soup, url)
            print("📄 Извлекаем ТОЛЬКО основной текст статьи...")
            clean_content = self.extract_clean_article_content(soup)
            word_count = self.count_words(clean_content)
            print(f"📊 ТОЧНОЕ количество слов: {word_count}")
            preview = clean_content[:200] + "..." if len(clean_content) > 200 else clean_content
            print(f"🔍 Первые символы: {preview}")
            if word_count > 500:
                print(f"📏 Статья слишком длинная ({word_count} слов > 500) - пропускаем")
                return None
            print(f"✅ Статья подходит ({word_count} слов ≤ 500)")
            summary = self.create_summary(clean_content, news_item['title'])
            image_url = self.extract_main_image(soup, url)
            return {
                'title': news_item['title'],
                'url': url,
                'content': clean_content,
                'summary': summary,
                'image_url': image_url,
                'publish_time': publish_time,
                'word_count': word_count
            }
        except Exception as e:
            print(f"❌ Ошибка обработки {url}: {e}")
            return None
    
    def extract_article_content(self, soup):
        """УСТАРЕВШИЙ метод - теперь вызывает правильный метод"""
        return self.extract_clean_article_content(soup)
    
    def create_summary(self, content, title):
        """Создает краткую выжимку"""
        if not content:
            return title
        sentences = re.split(r'[.!?]+', content)
        meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        if meaningful_sentences:
            summary = '. '.join(meaningful_sentences[:2])
            return summary + '.' if not summary.endswith('.') else summary
        return content[:200] + '...' if len(content) > 200 else content
    
    def extract_main_image(self, soup, base_url):
        """Извлекает главное изображение статьи"""
        image_selectors = [
            'meta[property="og:image"]',
            '.article-image img',
            '.news-image img',
            'article img',
            '.content img:first-of-type',
            '.main-image img',
            '.post-image img'
        ]
        for selector in image_selectors:
            if 'meta' in selector:
                img_elem = soup.select_one(selector)
                if img_elem:
                    image_url = img_elem.get('content', '')
            else:
                img_elem = soup.select_one(selector)
                if img_elem:
                    image_url = img_elem.get('src', '') or img_elem.get('data-src', '')
            if image_url:
                full_image_url = urljoin(base_url, image_url)
                if not any(small in image_url.lower() for small in ['icon', 'logo', 'thumb', 'avatar']):
                    return full_image_url
        return ''
    
    def get_latest_news(self, since_time: Optional[datetime] = None):
        """Получает новости из блока 'ГОЛОВНЕ ЗА ДОБУ' с умной фильтрацией"""
        print("🔍 Загружаем главную страницу Football.ua...")
        if since_time:
            print(f"🕒 Ищем новости с {since_time.strftime('%H:%M %d.%m.%Y')}")
        soup = self.get_page_content(self.base_url)
        if not soup:
            print("❌ Не удалось загрузить главную страницу")
            return []
        print("🎯 Ищем блок 'ГОЛОВНЕ ЗА ДОБУ'...")
        golovne_section = self.find_golovne_za_dobu_section(soup)
        if not golovne_section:
            print("❌ Блок 'ГОЛОВНЕ ЗА ДОБУ' не найден")
            return []
        print("📰 Извлекаем новости из блока...")
        news_items = self.extract_news_from_section(golovne_section, since_time)
        if not news_items:
            print("❌ Новости в блоке не найдены")
            return []
        print(f"✅ Найдено {len(news_items)} новостей в блоке 'ГОЛОВНЕ ЗА ДОБУ'")
        full_articles = []
        consecutive_old_articles = 0
        for i, news_item in enumerate(news_items, 1):
            print(f"📖 Обрабатываем новость {i}/{len(news_items)}: {news_item['title'][:50]}...")
            article_data = self.get_full_article_data(news_item, since_time)
            if article_data is None:
                if since_time:
                    soup_temp = self.get_page_content(news_item['url'])
                    if soup_temp:
                        publish_time = self.estimate_article_publish_time(soup_temp, news_item['url'])
                        if publish_time and publish_time <= since_time:
                            consecutive_old_articles += 1
                            print(f"⏰ Старая статья #{consecutive_old_articles} подряд (время: {publish_time.strftime('%H:%M %d.%m')})")
                            if consecutive_old_articles >= self.max_consecutive_old:
                                print(f"🚫 ОПТИМИЗАЦИЯ: {self.max_consecutive_old} статьи подряд оказались старыми - прекращаем обработку остальных")
                                print(f"⏭️ Пропускаем {len(news_items) - i} оставшихся статей")
                                break
                            continue
                        else:
                            consecutive_old_articles = 0
                            print(f"⏭️ Статья не подходит по длине/содержанию - пропускаем")
                            continue
                    else:
                        consecutive_old_articles = 0
                        print(f"⏭️ Техническая ошибка - пропускаем")
                        continue
                else:
                    print(f"⏭️ Статья не подходит - пропускаем")
                    continue
            consecutive_old_articles = 0
            full_articles.append(article_data)
            print(f"✅ Статья добавлена: {article_data['title'][:50]}...")
            time.sleep(1)
        print(f"✅ Обработано {len(full_articles)} подходящих статей")
        return full_articles

def get_latest_news(since_time: Optional[datetime] = None):
    """Функция-обертка для совместимости"""
    parser = FootballUATargetedParser()
    if since_time:
        since_time_buffered = since_time - timedelta(minutes=1)
        articles = parser.get_latest_news(since_time_buffered)
    else:
        articles = parser.get_latest_news()
    result = []
    for article in articles:
        result.append({
            'title': article['title'],
            'link': article['url'],
            'url': article['url'],
            'summary': article['summary'],
            'image_url': article['image_url'],
            'content': article['content'],
            'publish_time': article.get('publish_time'),
            'word_count': article.get('word_count'),
            'source': 'Football.ua'
        })
    return result

def test_targeted_parser():
    """Тестирование целевого парсера"""
    print("🎯 ТЕСТИРУЕМ ОПТИМИЗИРОВАННЫЙ ПАРСЕР ДЛЯ БЛОКА 'ГОЛОВНЕ ЗА ДОБУ'")
    print("=" * 60)
    print("\n📋 Тест 1: Получение всех новостей")
    parser = FootballUATargetedParser(max_consecutive_old=2)
    articles = parser.get_latest_news()
    if articles:
        print(f"✅ Найдено {len(articles)} новостей")
        for i, article in enumerate(articles, 1):
            publish_time = article.get('publish_time')
            word_count = article.get('word_count', 'неизвестно')
            time_str = publish_time.strftime('%H:%M %d.%m') if publish_time else 'неизвестно'
            print(f"   📰 {i}. {article['title'][:50]}... ({time_str}, {word_count} слов)")
    print(f"\n📋 Тест 2: Получение новостей за последние 30 минут (с оптимизацией)")
    since_time = datetime.now(KIEV_TZ) - timedelta(minutes=30)
    recent_articles = parser.get_latest_news(since_time)
    if recent_articles:
        print(f"✅ Найдено {len(recent_articles)} новых новостей")
        for i, article in enumerate(recent_articles, 1):
            publish_time = article.get('publish_time')
            word_count = article.get('word_count', 'неизвестно')
            time_str = publish_time.strftime('%H:%M %d.%m') if publish_time else 'неизвестно'
            print(f"   📰 {i}. {article['title'][:50]}... ({time_str}, {word_count} слов)")
    else:
        print("🔭 Новых новостей за последние 30 минут не найдено")
    print(f"\n📋 Тест 3: Демонстрация агрессивной оптимизации (max_consecutive_old=1)")
    aggressive_parser = FootballUATargetedParser(max_consecutive_old=1)
    since_time_old = datetime.now(KIEV_TZ) - timedelta(hours=2)
    aggressive_articles = aggressive_parser.get_latest_news(since_time_old)
    print(f"📊 С агрессивной оптимизацией найдено: {len(aggressive_articles)} статей")
    print(f"\n📋 Тест 4: Демонстрация правильного подсчета слов")
    test_texts = [
        "Это простой текст из пяти слов.",
        "Текст с    лишними   пробелами и знаками препинания!!!",
        "<p>HTML текст</p> с <strong>тегами</strong> и обычным текстом.",
        ""
    ]
    for test_text in test_texts:
        word_count = parser.count_words(test_text)
        print(f"   📝 \"{test_text[:30]}...\" → {word_count} слов")
    print("\n🚀 ПРЕИМУЩЕСТВА ОПТИМИЗАЦИИ:")
    print("   ✅ Быстрая проверка времени в начале обработки")
    print("   ✅ Прекращение обработки после N старых статей подряд")
    print("   ✅ Настраиваемый параметр max_consecutive_old")
    print("   ✅ Экономия времени и ресурсов")
    print("   ✅ Правильный подсчет слов в чистом контенте")

if __name__ == "__main__":
    test_targeted_parser()
