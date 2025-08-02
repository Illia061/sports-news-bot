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
        
        # НОВАЯ ЛОГИКА: Если указано время, получаем все новости для фильтрации
        # Если не указано, возвращаем первые 5 (старое поведение)
        if since_time:
            print(f"🕒 Фильтруем новости с {since_time.strftime('%H:%M %d.%m.%Y')}")
            return unique_news  # Возвращаем все для дальнейшей фильтрации по времени публикации
        else:
            return unique_news[:5]  # Старое поведение
    
    def is_news_link(self, href):
        """Проверяет, является ли ссылка новостной"""
        if not href:
            return False
        
        # Новостные разделы на football.ua
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
            r'/\d+[^/]*\.html'  # Ссылки с ID новостей
        ]
        
        return any(re.search(pattern, href) for pattern in news_patterns)
    
    def parse_ukrainian_date(self, date_text: str) -> Optional[datetime]:
        """Парсит украинский формат даты"""
        try:
            # Словарь украинских месяцев
            ukrainian_months = {
                'січня': 1, 'лютого': 2, 'березня': 3, 'квітня': 4, 'травня': 5, 'червня': 6,
                'липня': 7, 'серпня': 8, 'вересня': 9, 'жовтня': 10, 'листопада': 11, 'грудня': 12,
                'січ': 1, 'лют': 2, 'бер': 3, 'кві': 4, 'тра': 5, 'чер': 6,
                'лип': 7, 'сер': 8, 'вер': 9, 'жов': 10, 'лис': 11, 'гру': 12
            }
            
            # Очищаем текст
            cleaned_text = re.sub(r'[,.]', '', date_text.lower().strip())
            
            # Паттерн: "02 серпня 2025, 10:48"
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
            
            # Паттерн: "02.08.2025, 10:48"
            pattern2 = r'(\d{1,2})\.(\d{1,2})\.(\d{4})[\s,]+(\d{1,2}):(\d{2})'
            match2 = re.search(pattern2, cleaned_text)
            
            if match2:
                day = int(match2.group(1))
                month = int(match2.group(2))
                year = int(match2.group(3))
                hour = int(match2.group(4))
                minute = int(match2.group(5))
                return datetime(year, month, day, hour, minute, tzinfo=KIEV_TZ)
            
            # Паттерн: "10:48" (только время, берем сегодняшнюю дату)
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
            
            # Ищем мета-теги с датой
            meta_selectors = [
                'meta[property="article:published_time"]',
                'meta[name="publish_date"]',
                'meta[name="date"]',
                'meta[property="og:published_time"]',
                'meta[name="DC.date"]',
                'meta[itemprop="datePublished"]'
            ]
            
            for selector in meta_selectors:
                meta_tag = soup.select_one(selector)
                if meta_tag:
                    content = meta_tag.get('content', '')
                    if content:
                        print(f"📅 Найден мета-тег {selector}: {content}")
                        try:
                            # Пытаемся парсить ISO формат
                            if 'T' in content:
                                parsed_date = datetime.fromisoformat(content.replace('Z', '+00:00').replace('+00:00', ''))
                                # Преобразуем в киевское время
                                parsed_date_kiev = parsed_date.astimezone(KIEV_TZ)
                                print(f"✅ Успешно спарсен мета-тег: {parsed_date_kiev}")
                                return parsed_date_kiev
                        except Exception as e:
                            print(f"⚠️ Не удалось спарсить мета-тег: {e}")
                            continue
            
            # Ищем дату в тексте страницы
            date_selectors = [
                '.article-date',
                '.publish-date', 
                '.news-date',
                '.date',
                '.timestamp',
                'time[datetime]',
                '.article-time',
                '.post-date',
                '.entry-date',
                '[class*="date"]',
                '[class*="time"]'
            ]
            
            for selector in date_selectors:
                date_elem = soup.select_one(selector)
                if date_elem:
                    # Пытаемся получить datetime атрибут
                    datetime_attr = date_elem.get('datetime')
                    if datetime_attr:
                        print(f"📅 Найден datetime атрибут: {datetime_attr}")
                        try:
                            parsed_date = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00').replace('+00:00', ''))
                            # Преобразуем в киевское время
                            parsed_date_kiev = parsed_date.astimezone(KIEV_TZ)
                            print(f"✅ Успешно спарсен datetime: {parsed_date_kiev}")
                            return parsed_date_kiev
                        except Exception as e:
                            print(f"⚠️ Не удалось спарсить datetime: {e}")
                    
                    # Пытаемся получить текст даты
                    date_text = date_elem.get_text(strip=True)
                    if date_text:
                        print(f"📅 Найден текст даты в {selector}: '{date_text}'")
                        parsed_date = self.parse_ukrainian_date(date_text)
                        if parsed_date:
                            print(f"✅ Успешно спарсен текст даты: {parsed_date}")
                            return parsed_date
            
            # Ищем дату в заголовке страницы или в основном контенте
            all_text = soup.get_text()
            
            # Паттерны для поиска даты в тексте
            date_patterns = [
                r'(\d{1,2})\s+(січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)\s+(\d{4})[\s,]+(\d{1,2}):(\d{2})',
                r'(\d{1,2})\.(\d{1,2})\.(\d{4})[\s,]+(\d{1,2}):(\d{2})',
                r'(\d{1,2})/(\d{1,2})/(\d{4})[\s,]+(\d{1,2}):(\d{2})'
            ]
            
            for pattern in date_patterns:
                matches = re.findall(pattern, all_text, re.IGNORECASE)
                for match in matches[:3]:  # Проверяем только первые 3 совпадения
                    if len(match) >= 5:
                        try:
                            if 'січня' in pattern or 'лютого' in pattern:  # украинский формат
                                parsed_date = self.parse_ukrainian_date(' '.join(match))
                            else:  # числовой формат
                                day, month, year, hour, minute = map(int, match)
                                parsed_date = datetime(year, month, day, hour, minute, tzinfo=KIEV_TZ)
                            
                            if parsed_date:
                                print(f"✅ Найдена дата в тексте: {parsed_date}")
                                return parsed_date
                        except Exception as e:
                            print(f"⚠️ Ошибка парсинга найденной даты: {e}")
                            continue
            
            # ВАЖНО: Если не нашли точное время, НЕ возвращаем текущее время!
            print(f"⚠️ Не удалось определить точное время публикации")
            return None
            
        except Exception as e:
            print(f"⚠️ Ошибка определения времени публикации: {e}")
            return None
    
    def get_full_article_data(self, news_item, since_time: Optional[datetime] = None):
        """Получает полные данные статьи с проверкой времени"""
        url = news_item['url']
        soup = self.get_page_content(url)
        
        if not soup:
            return None
        
        try:
            # Определяем время публикации
            publish_time = self.estimate_article_publish_time(soup, url)
            
            # ИЗМЕНЕНА ЛОГИКА: Если указано время фильтрации, проверяем только при наличии точного времени
            if since_time and publish_time:
                if publish_time <= since_time:
                    print(f"⏰ Статья опубликована {publish_time.strftime('%H:%M %d.%m')} - пропускаем (до {since_time.strftime('%H:%M %d.%m')})")
                    return None
                else:
                    print(f"✅ Статья опубликована {publish_time.strftime('%H:%M %d.%m')} - новая!")
            elif since_time and not publish_time:
                # Если не смогли определить точное время, считаем статью новой
                print(f"⚠️ Время публикации не определено - считаем статью новой")
            
            # Извлекаем основной контент
            content = self.extract_article_content(soup)
            
            # Создаем краткую выжимку
            summary = self.create_summary(content, news_item['title'])
            
            # Ищем изображение
            image_url = self.extract_main_image(soup, url)
            
            return {
                'title': news_item['title'],
                'url': url,
                'content': content,
                'summary': summary,
                'image_url': image_url,
                'publish_time': publish_time
            }
            
        except Exception as e:
            print(f"❌ Ошибка обработки {url}: {e}")
            return None
    
    def extract_article_content(self, soup):
        """Извлекает основной текст статьи (РАСШИРЕННАЯ ВЕРСИЯ для AI)"""
        content_selectors = [
            '.article-content',
            '.news-content',
            '.post-content',
            '.content',
            'article',
            '.main-text',
            '.article-body',
            '.news-body'
        ]
        
        # Сначала пытаемся найти основной контейнер статьи
        main_content = ""
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # Убираем ненужные элементы
                for unwanted in content_elem.find_all(['script', 'style', 'iframe', 'div[class*="ad"]', 'div[class*="banner"]']):
                    unwanted.decompose()
                
                # Извлекаем все параграфы (не ограничиваем для AI)
                paragraphs = content_elem.find_all('p')
                if paragraphs:
                    main_content = '\n'.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])
                    break
        
        # Если основной контейнер не найден, ищем все параграфы на странице
        if not main_content:
            all_paragraphs = soup.find_all('p')
            meaningful_paragraphs = []
            
            for p in all_paragraphs:
                text = p.get_text(strip=True)
                # Фильтруем слишком короткие и служебные параграфы
                if (len(text) > 30 and 
                    not any(skip in text.lower() for skip in ['cookie', 'реклама', 'підпис', 'фото', 'джерело'])):
                    meaningful_paragraphs.append(text)
            
            # Берем больше контента для AI (до 1500 символов)
            main_content = '\n'.join(meaningful_paragraphs)
            if len(main_content) > 1500:
                sentences = re.split(r'[.!?]+', main_content)
                trimmed_content = ""
                for sentence in sentences:
                    if len(trimmed_content + sentence) < 1500:
                        trimmed_content += sentence + ". "
                    else:
                        break
                main_content = trimmed_content.strip()
        
        print(f"📄 Извлечено {len(main_content)} символов контента")
        return main_content
    
    def create_summary(self, content, title):
        """Создает краткую выжимку"""
        if not content:
            return title
        
        # Берем первые 2-3 предложения
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
                # Проверяем, что это не маленькая иконка
                if not any(small in image_url.lower() for small in ['icon', 'logo', 'thumb', 'avatar']):
                    return full_image_url
        
        return ''
    
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
