import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import time

def clean_text(text: str) -> str:
    """Очищает текст от лишних символов"""
    if not text or not isinstance(text, str):
        return ""
    
    # Удаляем разбитый текст (например, И. н. ш. е.)
    text = re.sub(r'(\w)\.\s*', r'\1', text)
    text = re.sub(r'\s*\.\s*', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ0-9.,!?:;\-]', '', text)
    return text

class FootballUATargetedParser:
    def __init__(self):
        self.base_url = "https://football.ua/"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html floats and doubles,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        })
    
    def get_page_content(self, url):
        """Получает содержимое страницы"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            response.encoding = 'utf-8'  # Явно устанавливаем UTF-8
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
            '.sidebar',
            '.right-column', 
            '.side-block',
            '.news-sidebar',
            '.daily-news',
            '.main-today',
            '.today-block',
            '.golovne',
            '[class*="today"]',
            '[class*="daily"]',
            '[class*="golovne"]'
        ]
        
        for selector in possible_selectors:
            elements = soup.select(selector)
            for element in elements:
                if re.search(r'головне.*за.*добу', element.get_text(), re.I):
                    print(f"✅ Найден блок через селектор: {selector}")
                    return element
        
        print("⚠️  Ищем блок через анализ структуры...")
        all_divs = soup.find_all(['div', 'section'], class_=True)
        
        for div in all_divs:
            div_text = div.get_text().lower()
            if 'головне' in div_text and 'добу' in div_text:
                print(f"✅ Найден блок с текстом 'головне за добу'")
                return div
        
        print("❌ Блок 'ГОЛОВНЕ ЗА ДОБУ' не найден")
        return None
    
    def extract_news_from_section(self, section):
        """Извлекает новости из найденной секции"""
        if not section:
            return []
        
        news_links = []
        all_links = section.find_all('a', href=True)
        
        print(f"🔍 Найдено {len(all_links)} ссылок в секции")
        
        for link in all_links:
            href = link.get('href', '')
            text = clean_text(link.get_text(strip=True))
            
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
        
        return unique_news[:5]
    
    def is_news_link(self, href):
        """Проверяет, является ли ссылка новостной"""
        if not href:
            return False
        
        news_patterns = [
            r'/news/',
            r'/ukraine/',
            r'/world/',
            r'/europe/',
            r'/england/',
            r'/spain/',
            r'/italy/',
            r'/germany/',
            r'/france/',
            r'/poland/',
            r'/\d+[^/]*\.html'
        ]
        
        return any(re.search(pattern, href) for pattern in news_patterns)
    
    def get_full_article_data(self, news_item):
        """Получает полные данные статьи"""
        url = news_item['url']
        soup = self.get_page_content(url)
        
        if not soup:
            return {
                'title': news_item['title'],
                'url': url,
                'content': '',
                'summary': news_item['title'],
                'image_url': ''
            }
        
        try:
            content = self.extract_article_content(soup)
            summary = self.create_summary(content, news_item['title'])
            image_url = self.extract_main_image(soup, url)
            
            return {
                'title': news_item['title'],
                'url': url,
                'content': clean_text(content),
                'summary': clean_text(summary),
                'image_url': image_url
            }
            
        except Exception as e:
            print(f"❌ Ошибка обработки {url}: {e}")
            return {
                'title': news_item['title'],
                'url': url,
                'content': '',
                'summary': news_item['title'],
                'image_url': ''
            }
    
    def extract_article_content(self, soup):
        """Извлекает основной текст статьи"""
        content_selectors = [
            '.article-content',
            '.news-content',
            '.post-content',
            '.content',
            'article',
            '.main-text'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                paragraphs = content_elem.find_all('p')
                if paragraphs:
                    return '\n'.join([clean_text(p.get_text(strip=True)) for p in paragraphs[:4]])
        
        paragraphs = soup.find_all('p')
        meaningful_paragraphs = [
            clean_text(p.get_text(strip=True)) for p in paragraphs 
            if len(p.get_text(strip=True)) > 30
        ]
        
        return '\n'.join(meaningful_paragraphs[:3]) if meaningful_paragraphs else ''
    
    def create_summary(self, content, title):
        """Создает краткую выжимку"""
        if not content:
            return clean_text(title)
        
        content = clean_text(content)
        sentences = [s.strip() for s in content.split('. ') if s.strip()]
        summary = '. '.join(sentences[:2]) + '.' if sentences else content[:200] + '...'
        return clean_text(summary)
    
    def extract_main_image(self, soup, base_url):
        """Извлекает главное изображение статьи"""
        image_selectors = [
            'meta[property="og:image"]',
            '.article-image img',
            '.news-image img',
            'article img',
            '.content img:first-of-type'
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
    
    def get_latest_news(self):
        """Основной метод - получает новости из блока 'ГОЛОВНЕ ЗА ДОБУ'"""
        print("🔍 Загружаем главную страницу Football.ua...")
        
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
        news_items = self.extract_news_from_section(golovne_section)
        
        if not news_items:
            print("❌ Новости в блоке не найдены")
            return []
        
        print(f"✅ Найдено {len(news_items)} новостей в блоке 'ГОЛОВНЕ ЗА ДОБУ'")
        
        full_articles = []
        
        for i, news_item in enumerate(news_items, 1):
            print(f"📖 Обрабатываем новость {i}/{len(news_items)}: {news_item['title'][:50]}...")
            article_data = self.get_full_article_data(news_item)
            full_articles.append(article_data)
            time.sleep(1)
        
        return full_articles

def get_latest_news():
    """Функция-обертка для совместимости"""
    parser = FootballUATargetedParser()
    articles = parser.get_latest_news()
    
    result = []
    for article in articles:
        result.append({
            'title': article['title'],
            'link': article['url'],
            'summary': article['summary'],
            'image_url': article['image_url'],
            'content': article['content']
        })
    
    return result

def test_targeted_parser():
    """Тестирование целевого парсера"""
    print("🎯 ТЕСТИРУЕМ ПАРСЕР ДЛЯ БЛОКА 'ГОЛОВНЕ ЗА ДОБУ'")
    print("=" * 60)
    
    parser = FootballUATargetedParser()
    articles = parser.get_latest_news()
    
    if articles:
        print(f"\n✅ УСПЕШНО! Найдено {len(articles)} новостей из блока 'ГОЛОВНЕ ЗА ДОБУ':")
        print("=" * 60)
        
        for i, article in enumerate(articles, 1):
            print(f"\n📰 НОВОСТЬ {i}")
            print(f"📌 Заголовок: {article['title']}")
            print(f"📝 Выжимка: {article['summary'][:100]}...")
            if article['image_url']:
                print(f"🖼️  Изображение: ✅")
                print(f"    URL: {article['image_url']}")
            else:
                print(f"🖼️  Изображение: ❌")
            print(f"🔗 Ссылка: {article['url']}")
            print("-" * 60)
    else:
        print("❌ Новости из блока 'ГОЛОВНЕ ЗА ДОБУ' не найдены")
        print("Возможные причины:")
        print("- Изменилась структура сайта")
        print("- Блок находится в другом месте")
        print("- Проблемы с подключением")

if __name__ == "__main__":
    test_targeted_parser()
