import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo
import google.generativeai as genai
import os

KIEV_TZ = ZoneInfo("Europe/Kiev")

class ESPNSoccerParser:
    def __init__(self):
        self.base_url = "https://www.espn.com/soccer/"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        })
        
        # Настройка AI для перевода
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.model = None
        self._init_translator()
    
    def _init_translator(self):
        """Инициализирует AI для перевода"""
        if self.gemini_api_key:
            try:
                genai.configure(api_key=self.gemini_api_key)
                self.model = genai.GenerativeModel("gemini-2.5-flash")
                print("✅ AI переводчик инициализирован")
            except Exception as e:
                print(f"❌ Ошибка инициализации AI переводчика: {e}")
                self.model = None
        else:
            print("⚠️ GEMINI_API_KEY не найден - перевод будет отключен")
    
    def get_page_content(self, url):
        """Получает содержимое страницы"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"Ошибка загрузки {url}: {e}")
            return None
    
    def find_top_headlines_section(self, soup):
        """Находит блок 'Top Headlines' на ESPN Soccer"""
        
        # Способ 1: Поиск по точному тексту заголовка
        header_texts = [
            "Top Headlines",
            "top headlines",
            "Headlines"
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
        
        # Способ 2: Поиск по специфичным для ESPN классам
        possible_selectors = [
            # ESPN специфичные селекторы
            '.contentItem',
            '.headlines',
            '.top-headlines',
            '.news-feed',
            '.contentItem__content',
            '.story-feed',
            
            # Общие селекторы для новостных блоков
            '[class*="headline"]',
            '[class*="story"]',
            '[class*="news"]',
            '.col-a',  # ESPN использует колоночную сетку
            '.col-one'
        ]
        
        for selector in possible_selectors:
            elements = soup.select(selector)
            for element in elements:
                # Проверяем, содержит ли элемент ссылки на футбольные новости
                links = element.find_all('a', href=True)
                soccer_links = [link for link in links if self.is_soccer_news_link(link.get('href', ''))]
                
                if len(soccer_links) >= 3:  # Если есть минимум 3 футбольные ссылки
                    print(f"✅ Найден блок с футбольными новостями через селектор: {selector}")
                    return element
        
        # Способ 3: Поиск основного контента страницы
        print("⚠️ Ищем футбольные новости в основном контенте...")
        
        main_content_selectors = [
            'main',
            '#main-container',
            '.main-content',
            '.page-container',
            'body'
        ]
        
        for selector in main_content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                # Ищем все ссылки на футбольные новости
                all_links = main_content.find_all('a', href=True)
                soccer_links = []
                
                for link in all_links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    if self.is_soccer_news_link(href) and len(text) > 10:
                        soccer_links.append(link)
                
                if len(soccer_links) >= 5:  # Если нашли достаточно футбольных ссылок
                    print(f"✅ Найдено {len(soccer_links)} футбольных новостей в {selector}")
                    # Создаем виртуальный контейнер с найденными ссылками
                    virtual_container = soup.new_tag('div')
                    for link in soccer_links[:10]:  # Берем первые 10
                        virtual_container.append(link.parent or link)
                    return virtual_container
        
        print("❌ Блок с футбольными новостями не найден")
        return None
    
    def is_soccer_news_link(self, href):
        """Проверяет, является ли ссылка футбольной новостью ESPN"""
        if not href:
            return False
        
        # ESPN футбольные URL паттерны
        soccer_patterns = [
            r'/soccer/',
            r'/football/',  # Европейский футбол на ESPN
            r'/story/_/id/\d+',  # Общий паттерн статей ESPN
            r'/news/story/',
            r'espn.com/soccer',
            r'premier-league',
            r'champions-league',
            r'la-liga',
            r'serie-a',
            r'bundesliga',
            r'ligue-1',
            r'mls',
            r'uefa',
            r'fifa'
        ]
        
        # Проверяем, что это не служебные ссылки
        exclude_patterns = [
            r'/video/',
            r'/watch/',
            r'/fantasy/',
            r'/betting/',
            r'/schedule/',
            r'/standings/',
            r'/stats/',
            r'/teams/',
            r'/players/',
            r'/scores/',
            r'#',
            r'javascript:',
            r'mailto:',
            r'/podcast/'
        ]
        
        # Исключаем служебные ссылки
        if any(re.search(pattern, href, re.I) for pattern in exclude_patterns):
            return False
        
        # Проверяем футбольные паттерны
        return any(re.search(pattern, href, re.I) for pattern in soccer_patterns)
    
    def extract_news_from_section(self, section, since_time: Optional[datetime] = None):
        """Извлекает новости из найденной секции"""
        if not section:
            return []
        
        news_links = []
        
        # Ищем все ссылки в секции
        all_links = section.find_all('a', href=True)
        
        print(f"🔍 Найдено {len(all_links)} ссылок в секции")
        
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Фильтруем только футбольные новостные ссылки
            if self.is_soccer_news_link(href) and len(text) > 15:
                # Формируем полный URL
                if href.startswith('/'):
                    full_url = f"https://www.espn.com{href}"
                elif href.startswith('http'):
                    full_url = href
                else:
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
        
        # Возвращаем новости (при указании времени - все для фильтрации, иначе - первые 8)
        if since_time:
            return unique_news
        else:
            return unique_news[:8]
    
    def translate_to_ukrainian(self, text: str, context: str = "футбольна новина") -> str:
        """Переводит текст с английского на украинский с помощью AI"""
        if not self.model or not text:
            return text
        
        # Очищаем текст от лишних символов
        clean_text = re.sub(r'\s+', ' ', text).strip()
        
        if len(clean_text) < 5:
            return text
        
        prompt = f"""Переклади наступний текст з англійської на українську мову. Це {context}.

ВАЖЛИВІ ПРАВИЛА:
1. Зберігай футбольну термінологію (назви команд, ліг, турнірів)
2. Використовуй природну українську мову
3. Адаптуй для українського читача
4. Зберігай емоційний тон оригіналу
5. Назви команд залишай англійською або використовуй загальноприйняті українські назви
6. НЕ додавай зайвих пояснень - тільки переклад

ТЕКСТ ДЛЯ ПЕРЕКЛАДУ:
{clean_text}

ПЕРЕКЛАД:"""

        try:
            response = self.model.generate_content(prompt)
            translated = response.text.strip()
            
            # Очищаем перевод от возможных артефактов
            translated = re.sub(r'^(ПЕРЕКЛАД:|Переклад:)\s*', '', translated)
            translated = translated.strip()
            
            print(f"🌐 Переведено: {clean_text[:30]}... → {translated[:30]}...")
            return translated
            
        except Exception as e:
            print(f"❌ Ошибка перевода: {e}")
            return text
    
    def parse_espn_date(self, date_text: str) -> Optional[datetime]:
        """Парсит дату ESPN (обычно в формате '4h ago', 'Yesterday', etc.)"""
        try:
            if not date_text:
                return None
            
            current_time = datetime.now(KIEV_TZ)
            date_text = date_text.lower().strip()
            
            # "X hours ago"
            hours_match = re.search(r'(\d+)h\s*ago', date_text)
            if hours_match:
                hours = int(hours_match.group(1))
                return current_time - timedelta(hours=hours)
            
            # "X minutes ago"
            minutes_match = re.search(r'(\d+)m\s*ago', date_text)
            if minutes_match:
                minutes = int(minutes_match.group(1))
                return current_time - timedelta(minutes=minutes)
            
            # "X days ago"
            days_match = re.search(r'(\d+)d\s*ago', date_text)
            if days_match:
                days = int(days_match.group(1))
                return current_time - timedelta(days=days)
            
            # "Yesterday"
            if 'yesterday' in date_text:
                return current_time - timedelta(days=1)
            
            # "Today"
            if 'today' in date_text:
                return current_time.replace(hour=12, minute=0, second=0, microsecond=0)
            
            # Если не смогли распарсить, возвращаем None
            return None
            
        except Exception as e:
            print(f"⚠️ Ошибка парсинга даты ESPN '{date_text}': {e}")
            return None
    
    def estimate_article_publish_time(self, soup, url: str) -> Optional[datetime]:
        """Определяет время публикации статьи ESPN"""
        try:
            print(f"🕒 Определяем время публикации ESPN: {url}")
            
            # ESPN специфичные селекторы времени
            time_selectors = [
                'time[datetime]',
                '.timestamp',
                '.article-meta time',
                '.byline time',
                '[data-date]',
                '.publish-date',
                '.article-date',
                '[class*="time"]',
                '[class*="date"]'
            ]
            
            for selector in time_selectors:
                time_elem = soup.select_one(selector)
                if time_elem:
                    # Пытаемся получить datetime атрибут
                    datetime_attr = time_elem.get('datetime') or time_elem.get('data-date')
                    if datetime_attr:
                        try:
                            parsed_date = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                            parsed_date_kiev = parsed_date.astimezone(KIEV_TZ)
                            print(f"✅ Время из атрибута: {parsed_date_kiev}")
                            return parsed_date_kiev
                        except Exception as e:
                            print(f"⚠️ Ошибка парсинга datetime атрибута: {e}")
                    
                    # Пытаемся получить текст времени
                    time_text = time_elem.get_text(strip=True)
                    if time_text:
                        parsed_time = self.parse_espn_date(time_text)
                        if parsed_time:
                            print(f"✅ Время из текста: {parsed_time}")
                            return parsed_time
            
            # Ищем время в мета-тегах
            meta_selectors = [
                'meta[property="article:published_time"]',
                'meta[name="publish_date"]',
                'meta[property="og:published_time"]'
            ]
            
            for selector in meta_selectors:
                meta_tag = soup.select_one(selector)
                if meta_tag:
                    content = meta_tag.get('content', '')
                    if content:
                        try:
                            parsed_date = datetime.fromisoformat(content.replace('Z', '+00:00'))
                            parsed_date_kiev = parsed_date.astimezone(KIEV_TZ)
                            print(f"✅ Время из мета-тега: {parsed_date_kiev}")
                            return parsed_date_kiev
                        except Exception as e:
                            print(f"⚠️ Ошибка парсинга мета-даты: {e}")
            
            # Если не нашли время, возвращаем None (не текущее время!)
            print(f"⚠️ Не удалось определить время публикации ESPN")
            return None
            
        except Exception as e:
            print(f"⚠️ Ошибка определения времени публикации ESPN: {e}")
            return None
    
    def extract_article_content(self, soup):
        """Извлекает основной текст статьи ESPN"""
        content_selectors = [
            '.article-body',
            '.story-body',
            '.RichTextStoryBody',
            '.Story__Body',
            '.ArticleBody',
            '[data-module="ArticleBody"]',
            '.story-text',
            '.article-content'
        ]
        
        main_content = ""
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # Убираем ненужные элементы
                for unwanted in content_elem.find_all(['script', 'style', 'iframe', 'aside', '[class*="ad"]']):
                    unwanted.decompose()
                
                # Извлекаем параграфы
                paragraphs = content_elem.find_all('p')
                if paragraphs:
                    main_content = '\n'.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])
                    break
        
        # Если основной контейнер не найден, ищем все параграфы
        if not main_content:
            all_paragraphs = soup.find_all('p')
            meaningful_paragraphs = []
            
            for p in all_paragraphs:
                text = p.get_text(strip=True)
                # Фильтруем короткие и служебные параграфы
                if (len(text) > 30 and 
                    not any(skip in text.lower() for skip in ['cookie', 'advertisement', 'subscribe', 'follow us'])):
                    meaningful_paragraphs.append(text)
            
            main_content = '\n'.join(meaningful_paragraphs[:5])  # Первые 5 значимых параграфов
        
        print(f"📄 Извлечено {len(main_content)} символов контента ESPN")
        return main_content
    
    def extract_main_image(self, soup, base_url):
        """Извлекает главное изображение статьи ESPN"""
        image_selectors = [
            'meta[property="og:image"]',
            '.article-figure img',
            '.story-header img',
            '.media-wrapper img',
            '.hero-image img',
            '.featured-image img',
            'figure img:first-of-type',
            '.article-body img:first-of-type'
        ]
        
        for selector in image_selectors:
            if 'meta' in selector:
                img_elem = soup.select_one(selector)
                if img_elem:
                    image_url = img_elem.get('content', '')
            else:
                img_elem = soup.select_one(selector)
                if img_elem:
                    image_url = img_elem.get('src', '') or img_elem.get('data-src', '') or img_elem.get('data-original', '')
            
            if image_url:
                # Формируем полный URL
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                elif image_url.startswith('/'):
                    image_url = 'https://www.espn.com' + image_url
                elif not image_url.startswith('http'):
                    image_url = urljoin(base_url, image_url)
                
                # Проверяем, что это не маленькая иконка
                if not any(small in image_url.lower() for small in ['icon', 'logo', 'thumb', 'avatar', '/16x', '/32x']):
                    return image_url
        
        return ''
    
    def get_full_article_data(self, news_item, since_time: Optional[datetime] = None):
        """Получает полные данные статьи ESPN с переводом"""
        url = news_item['url']
        soup = self.get_page_content(url)
        
        if not soup:
            return None
        
        try:
            # Определяем время публикации
            publish_time = self.estimate_article_publish_time(soup, url)
            
            # Проверяем время публикации если указано
            if since_time and publish_time:
                if publish_time <= since_time:
                    print(f"⏰ ESPN статья опубликована {publish_time.strftime('%H:%M %d.%m')} - пропускаем")
                    return None
                else:
                    print(f"✅ ESPN статья опубликована {publish_time.strftime('%H:%M %d.%m')} - новая!")
            elif since_time and not publish_time:
                print(f"⚠️ Время публикации ESPN не определено - считаем статью новой")
            
            # Извлекаем контент
            original_content = self.extract_article_content(soup)
            original_title = news_item['title']
            
            # Переводим заголовок и контент
            print(f"🌐 Переводим заголовок...")
            translated_title = self.translate_to_ukrainian(original_title, "заголовок футбольної новини")
            
            print(f"🌐 Переводим контент...")
            translated_content = self.translate_to_ukrainian(original_content, "текст футбольної новини")
            
            # Создаем краткую выжимку на украинском
            summary = self.create_ukrainian_summary(translated_content, translated_title)
            
            # Ищем изображение
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
                'source': 'ESPN Soccer'
            }
            
        except Exception as e:
            print(f"❌ Ошибка обработки ESPN {url}: {e}")
            return None
    
    def create_ukrainian_summary(self, content, title):
        """Создает краткую выжимку на украинском языке"""
        if not content:
            return title
        
        # Берем первые 2-3 предложения
        sentences = re.split(r'[.!?]+', content)
        meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        if meaningful_sentences:
            summary = '. '.join(meaningful_sentences[:2])
            return summary + '.' if not summary.endswith('.') else summary
        
        return content[:200] + '...' if len(content) > 200 else content
    
    def get_latest_news(self, since_time: Optional[datetime] = None):
        """Основной метод - получает новости ESPN Soccer с переводом"""
        print("🔍 Загружаем страницу ESPN Soccer...")
        
        if since_time:
            print(f"🕒 Ищем ESPN новости с {since_time.strftime('%H:%M %d.%m.%Y')}")
        
        soup = self.get_page_content(self.base_url)
        if not soup:
            print("❌ Не удалось загрузить страницу ESPN Soccer")
            return []
        
        print("🎯 Ищем блок 'Top Headlines' на ESPN...")
        headlines_section = self.find_top_headlines_section(soup)
        
        if not headlines_section:
            print("❌ Блок 'Top Headlines' не найден на ESPN")
            return []
        
        print("📰 Извлекаем новости из блока ESPN...")
        news_items = self.extract_news_from_section(headlines_section, since_time)
        
        if not news_items:
            print("❌ Новости ESPN в блоке не найдены")
            return []
        
        print(f"✅ Найдено {len(news_items)} новостей ESPN")
        
        # Обрабатываем и переводим каждую новость
        full_articles = []
        
        for i, news_item in enumerate(news_items, 1):
            print(f"📖 Обрабатываем ESPN новость {i}/{len(news_items)}: {news_item['title'][:50]}...")
            
            article_data = self.get_full_article_data(news_item, since_time)
            
            if since_time and article_data is None:
                print(f"🛑 Обнаружена старая ESPN новость, прекращаем обработку")
                break
            
            if article_data:
                full_articles.append(article_data)
            
            # Пауза между запросами к ESPN
            time.sleep(2)
        
        print(f"✅ Обработано {len(full_articles)} новых статей ESPN с переводом")
        return full_articles


# Функция для интеграции с существующей системой
def get_espn_news(since_time: Optional[datetime] = None):
    """Функция для получения новостей ESPN Soccer с переводом"""
    parser = ESPNSoccerParser()
    articles = parser.get_latest_news(since_time)
    
    # Конвертируем в формат, ожидаемый основным кодом
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
            'source': 'ESPN Soccer',
            'original_title': article.get('original_title', ''),
            'original_content': article.get('original_content', '')
        })
    
    return result


def test_espn_parser():
    """Тестирование ESPN парсера"""
    print("🧪 ТЕСТИРУЕМ ESPN SOCCER PARSER")
    print("=" * 60)
    
    parser = ESPNSoccerParser()
    
    # Тест 1: Получение новостей
    print("\n📋 Тест 1: Получение новостей ESPN")
    articles = parser.get_latest_news()
    
    if articles:
        print(f"✅ Найдено {len(articles)} новостей ESPN")
        for i, article in enumerate(articles, 1):
            publish_time = article.get('publish_time')
            time_str = publish_time.strftime('%H:%M %d.%m') if publish_time else 'неизвестно'
            print(f"   📰 {i}. {article['title'][:60]}... ({time_str})")
            print(f"      🌐 Оригинал: {article.get('original_title', '')[:60]}...")
            print(f"      🖼️ Изображение: {'✅' if article.get('image_url') else '❌'}")
    else:
        print("❌ Новости ESPN не найдены")
    
    # Тест 2: Перевод
    if articles:
        print(f"\n📋 Тест 2: Качество перевода")
        test_article = articles[0]
        print(f"🔤 Оригинальный заголовок: {test_article.get('original_title', '')}")
        print(f"🌐 Переведенный заголовок: {test_article['title']}")
        
        original_summary = test_article.get('original_content', '')[:200]
        translated_summary = test_article.get('content', '')[:200]
        print(f"🔤 Оригинальный текст: {original_summary}...")
        print(f"🌐 Переведенный текст: {translated_summary}...")


if __name__ == "__main__":
    test_espn_parser()