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
    def __init__(self):
        self.base_url = "https://football.ua/"
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
        
        # Способ 1: Поиск по точному тексту заголовка
        header_texts = [
            "ГОЛОВНЕ ЗА ДОБУ",
            "головне за добу", 
            "Головне за добу"
        ]
        
        for header_text in header_texts:
            # Ищем элемент с таким текстом
            header_element = soup.find(text=re.compile(header_text, re.I))
            if header_element:
                print(f"✅ Найден заголовок: '{header_text}'")
                
                # Находим родительский контейнер секции
                parent = header_element.parent
                while parent and parent.name not in ['section', 'div', 'article']:
                    parent = parent.parent
                
                if parent:
                    # Ищем контейнер со списком новостей
                    news_container = parent.find_next(['div', 'ul', 'section'])
                    if news_container:
                        print(f"✅ Найден контейнер новостей после заголовка")
                        return news_container
                    else:
                        return parent
        
        # Способ 2: Поиск по классам, которые могут содержать этот блок
        possible_selectors = [
            # Селекторы для боковой панели/колонки
            '.sidebar',
            '.right-column', 
            '.side-block',
            '.news-sidebar',
            
            # Селекторы для блоков новостей
            '.daily-news',
            '.main-today',
            '.today-block',
            '.golovne',
            
            # Общие селекторы
            '[class*="today"]',
            '[class*="daily"]',
            '[class*="golovne"]'
        ]
        
        for selector in possible_selectors:
            elements = soup.select(selector)
            for element in elements:
                # Проверяем, содержит ли элемент текст "головне за добу"
                if re.search(r'головне.*за.*добу', element.get_text(), re.I):
                    print(f"✅ Найден блок через селектор: {selector}")
                    return element
        
        # Способ 3: Поиск всех блоков на странице, содержащих новости
        print("⚠️  Ищем блок через анализ структуры...")
        
        # Ищем все блоки, которые содержат ссылки на новости
        all_divs = soup.find_all(['div', 'section'], class_=True)
        
        for div in all_divs:
            # Проверяем, есть ли в блоке текст "головне за добу"
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
        
        # Ищем все ссылки в секции
        all_links = section.find_all('a', href=True)
        
        print(f"🔍 Найдено {len(all_links)} ссылок в секции")
        
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Фильтруем только новостные ссылки
            if self.is_news_link(href) and len(text) > 10:
                full_url = urljoin(self.base_url, href)
                news_links.append({
                    'title': text,
                    'url': full_url,
                    'href': href
                })
                
                print(f"📰 Найдена новость: {text[:50]}...")
        
        # Убираем дубликаты по URL
        seen_urls = set()
        unique_news = []
        
        for news in news_links:
            if news['url'] not in seen_urls:
                unique_news.append(news)
                seen_urls.add(news['url'])
        
        return unique_news
    
    def is_news_link(self, href: str) -> bool:
        """Проверяет, является ли ссылка новостью"""
        return bool(re.match(r'/(?:[\w-]+/)?\d{6}-[\w-]+\.html$', href))
    
    def parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Парсит строку даты с учетом украинских месяцев"""
        if not date_str:
            return None
        month_map = {
            'січня': '01', 'лютого': '02', 'березня': '03',
            'квітня': '04', 'травня': '05', 'червня': '06',
            'липня': '07', 'серпня': '08', 'вересня': '09',
            'жовтня': '10', 'листопада': '11', 'грудня': '12'
        }
        for uk_month, num in month_map.items():
            if uk_month in date_str.lower():
                date_str = re.sub(uk_month, num, date_str, flags=re.I)
                break
        date_formats = [
            '%d %m %Y %H:%M', '%d.%m.%Y %H:%M', '%d %m %Y',
            '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S', '%d.%m.%Y'
        ]
        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.replace(tzinfo=KIEV_TZ)
            except ValueError:
                continue
        print(f"⚠️ Не удалось распарсить дату: '{date_str}'")
        return None
    
    def get_article_publish_time(self, soup, url) -> Optional[datetime]:
        """Извлекает время публикации статьи"""
        print(f"🕒 Определяем время публикации для: {url}")
        
        # Новые селекторы: meta-теги сначала
        meta_selectors = [
            ('meta[property="og:published_time"]', 'content'),
            ('meta[name="published"]', 'content'),
            ('meta[itemprop="datePublished"]', 'content'),
            ('time[datetime]', 'datetime'),  # Для <time datetime="...">
        ]
        for selector, attr in meta_selectors:
            elem = soup.select_one(selector)
            if elem:
                date_str = elem.get(attr, '').strip()
                if date_str:
                    print(f"📅 Найден meta/тег: '{date_str}'")
                    parsed_date = self.parse_date_string(date_str)
                    if parsed_date:
                        return parsed_date
        
        # Существующие селекторы как fallback
        date_selectors = [
            '.news-date',
            '.article-date',
            '.publish-date',
            '[class*="date"]',
        ]
        for selector in date_selectors:
            date_elem = soup.select_one(selector)
            if date_elem:
                date_str = date_elem.get_text(strip=True)
                print(f"📅 Найден текст даты в {selector}: '{date_str}'")
                parsed_date = self.parse_date_string(date_str)
                if parsed_date:
                    return parsed_date
        
        # Fallback: Текущая дата минус 5 минут, если ничего не найдено
        print("⚠️ Дата не найдена, используем fallback")
        return datetime.now(KIEV_TZ) - timedelta(minutes=5)
    
    def extract_article_content(self, soup) -> str:
        """Извлекает полный текст статьи"""
        content_selectors = [
            '.news-full-content',
            '.article-body',
            '.post-content',
            '[itemprop="articleBody"]',
            '.news-text'
        ]
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                for unwanted in content_div.find_all(['script', 'style', 'ads', 'aside']):
                    unwanted.decompose()
                return ' '.join(content_div.get_text(strip=True).split())
        paragraphs = soup.find_all('p')
        return ' '.join(p.get_text(strip=True) for p in paragraphs)
    
    def extract_article_summary(self, soup, content: str) -> str:
        """Извлекает краткое описание"""
        meta_summary = soup.select_one('meta[name="description"]')
        if meta_summary:
            return meta_summary.get('content', '')[:300]
        intro = soup.select_one('.news-intro, .lead, p:first-of-type')
        if intro:
            return intro.get_text(strip=True)[:300]
        return content[:300] + '...' if content else ''
    
    def extract_article_image(self, soup, base_url: str) -> str:
        """Извлекает URL изображения статьи"""
        image_selectors = [
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
            '.news-image img',
            '.article-content img:first-of-type',
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
                # Проверяем, что это не маленькая иконка
                if not any(small in image_url.lower() for small in ['icon', 'logo', 'thumb', 'avatar']):
                    return full_image_url
        
        return ''
    
    def get_full_article_data(self, news_item: Dict[str, str], since_time: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """Загружает и извлекает полные данные статьи"""
        url = news_item['url']
        soup = self.get_page_content(url)
        if not soup:
            print(f"❌ Не удалось загрузить статью: {url}")
            return None
        
        publish_time = self.get_article_publish_time(soup, url)
        
        # Фильтрация по времени
        if since_time and publish_time < since_time:
            print(f"⏰ Статья старая ({publish_time.strftime('%H:%M %d.%m')}), пропускаем")
            return None
        
        content = self.extract_article_content(soup)
        
        # Доработка: Проверка на количество слов
        word_count = len(content.split())
        if word_count > 450:
            print(f"📏 Статья слишком длинная ({word_count} слов), пропускаем")
            return None
        
        summary = self.extract_article_summary(soup, content)
        image_url = self.extract_article_image(soup, url)
        
        return {
            'title': news_item['title'],
            'url': url,
            'content': content,
            'summary': summary,
            'image_url': image_url,
            'publish_time': publish_time
        }
    
    def get_latest_news(self, since_time: Optional[datetime] = None):
        """Основной метод - получает новости из блока 'ГОЛОВНЕ ЗА ДОБУ' с фильтрацией по времени"""
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
        
        # Получаем полные данные для каждой новости
        full_articles = []
        
        for i, news_item in enumerate(news_items, 1):
            print(f"📖 Обрабатываем новость {i}/{len(news_items)}: {news_item['title'][:50]}...")
            
            article_data = self.get_full_article_data(news_item, since_time)
            
            # Если статья не подходит по времени или длине, пропускаем, но продолжаем обработку остальных
            if article_data is None:
                print(f"🛑 Пропускаем (старая/длинная новость): {news_item['title'][:50]}...")
                continue
            
            # Если статья подходит по времени, добавляем её
            if article_data:
                full_articles.append(article_data)
            
            # Небольшая пауза между запросами
            time.sleep(1)
        
        print(f"✅ Обработано {len(full_articles)} новых статей")
        return full_articles

# Функция для совместимости с существующим кодом
def get_latest_news(since_time: Optional[datetime] = None):
    """Функция-обертка для совместимости"""
    parser = FootballUATargetedParser()
    articles = parser.get_latest_news(since_time)
    
    # Конвертируем в формат, ожидаемый основным кодом
    result = []
    for article in articles:
        result.append({
            'title': article['title'],
            'link': article['url'],  # main.py ожидает 'link', а не 'url'
            'url': article['url'],   # добавляем и 'url' для ai_processor
            'summary': article['summary'],
            'image_url': article['image_url'],
            'content': article['content'],  # ВАЖНО: полный контент для AI
            'publish_time': article.get('publish_time')  # НОВОЕ: время публикации
        })
    
    return result

def test_targeted_parser():
    """Тестирование целевого парсера"""
    print("🎯 ТЕСТИРУЕМ ПАРСЕР ДЛЯ БЛОКА 'ГОЛОВНЕ ЗА ДОБУ'")
    print("=" * 60)
    
    # Тест 1: Получение всех новостей (старое поведение)
    print("\n📋 Тест 1: Получение всех новостей")
    parser = FootballUATargetedParser()
    articles = parser.get_latest_news()
    
    if articles:
        print(f"✅ Найдено {len(articles)} новостей")
        for i, article in enumerate(articles, 1):
            publish_time = article.get('publish_time')
            time_str = publish_time.strftime('%H:%M %d.%m') if publish_time else 'неизвестно'
            print(f"   📰 {i}. {article['title'][:50]}... ({time_str})")
    
    # Тест 2: Получение новостей с фильтрацией по времени
    print(f"\n📋 Тест 2: Получение новостей за последние 30 минут")
    since_time = datetime.now(KIEV_TZ) - timedelta(minutes=30)
    recent_articles = parser.get_latest_news(since_time)
    
    if recent_articles:
        print(f"✅ Найдено {len(recent_articles)} новых новостей")
        for i, article in enumerate(recent_articles, 1):
            publish_time = article.get('publish_time')
            time_str = publish_time.strftime('%H:%M %d.%m') if publish_time else 'неизвестно'
            print(f"   📰 {i}. {article['title'][:50]}... ({time_str})")
    else:
        print("📭 Новых новостей за последние 30 минут не найдено")

if __name__ == "__main__":
    test_targeted_parser()
