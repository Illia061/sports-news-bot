
import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin, urlparse

class FootballUAParser:
    def __init__(self):
        self.base_url = "https://football.ua/"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8,ru;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0"
        })
    
    def get_page_content(self, url):
        """Получает содержимое страницы с обработкой ошибок"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            print(f"Ошибка при загрузке {url}: {e}")
            return None
    
    def find_main_today_section(self, soup):
        """Ищет раздел 'Головне за добу' различными способами"""
        
        # Способ 1: Поиск по тексту заголовка
        possible_headers = [
            "головне за добу", "головне", "за добу", 
            "головні новини", "топ новини", "найважливіше"
        ]
        
        for header_text in possible_headers:
            # Ищем заголовок секции
            header = soup.find(text=re.compile(header_text, re.I))
            if header:
                # Ищем родительский контейнер
                section = header.find_parent(['section', 'div', 'article'])
                if section:
                    print(f"Найдена секция по заголовку: '{header_text}'")
                    return section
        
        # Способ 2: Поиск по классам и атрибутам
        section_selectors = [
            {'class': re.compile(r'main.*today|today.*main|головне|main.*news', re.I)},
            {'data-section': re.compile(r'main|today|головне', re.I)},
            {'id': re.compile(r'main.*today|today.*main|головне', re.I)}
        ]
        
        for selector in section_selectors:
            section = soup.find(['section', 'div'], attrs=selector)
            if section:
                print(f"Найдена секция по селектору: {selector}")
                return section
        
        # Способ 3: Поиск основного блока новостей
        main_selectors = [
            'section.main-news-feed',
            'div.main-news-feed', 
            '.main-news',
            '.news-main',
            'main .news',
            '.main-content',
            '#main-content'
        ]
        
        for selector in main_selectors:
            section = soup.select_one(selector)
            if section:
                print(f"Найдена основная секция: {selector}")
                return section
        
        print("Специфичная секция не найдена, используем основной контент")
        return soup
    
    def extract_news_links(self, section):
        """Извлекает ссылки на новости из секции"""
        articles = []
        
        # Различные селекторы для ссылок
        link_patterns = [
            'a[href*="/news/"]',
            'a[href*="/ukraine/"]',
            'a[href*="/world/"]',
            'a.main-news-feed__link',
            'a.news-link',
            'a.article-link',
            '.news-item a',
            '.post-title a',
            'article a',
            'h1 a, h2 a, h3 a, h4 a'  # Заголовки с ссылками
        ]
        
        found_links = set()  # Избегаем дублирования
        
        for pattern in link_patterns:
            links = section.select(pattern)
            print(f"Найдено {len(links)} ссылок по паттерну: {pattern}")
            
            for link in links:
                href = link.get('href')
                if not href or href in found_links:
                    continue
                    
                # Получаем заголовок
                title = self.extract_title(link)
                if not title or len(title) < 10:
                    continue
                
                # Формируем полную ссылку
                full_url = urljoin(self.base_url, href)
                
                # Проверяем, что это новостная ссылка
                if self.is_news_link(full_url):
                    articles.append({
                        'title': title.strip(),
                        'link': full_url,
                        'pattern': pattern
                    })
                    found_links.add(href)
        
        # Сортируем по релевантности (новости из /news/ первыми)
        articles.sort(key=lambda x: (
            0 if '/news/' in x['link'] else 1,
            len(x['title'])  # Более длинные заголовки вперед
        ))
        
        return articles[:5]  # Возвращаем только первые 5
    
    def extract_title(self, link_element):
        """Извлекает заголовок из элемента ссылки"""
        # Пробуем получить текст из самой ссылки
        title = link_element.get_text(strip=True)
        
        if title:
            return title
        
        # Если в ссылке нет текста, ищем в родительских элементах
        for parent in [link_element.parent, link_element.parent.parent if link_element.parent else None]:
            if parent:
                title = parent.get_text(strip=True)
                if title and title != link_element.get_text(strip=True):
                    return title
        
        # Ищем title или alt атрибуты
        title = link_element.get('title') or link_element.get('alt')
        if title:
            return title
        
        return ""
    
    def is_news_link(self, url):
        """Проверяет, является ли ссылка новостной"""
        if not url:
            return False
            
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Новостные разделы
        news_sections = ['/news/', '/ukraine/', '/world/', '/europe/', '/championships/']
        
        return any(section in path for section in news_sections)
    
    def get_latest_news(self):
        """Основной метод для получения новостей"""
        print("Загружаем главную страницу Football.ua...")
        
        soup = self.get_page_content(self.base_url)
        if not soup:
            return []
        
        print("Ищем раздел 'Головне за добу'...")
        main_section = self.find_main_today_section(soup)
        
        if not main_section:
            print("Не удалось найти основную секцию новостей")
            return []
        
        print("Извлекаем ссылки на новости...")
        articles = self.extract_news_links(main_section)
        
        print(f"Найдено {len(articles)} статей")
        return articles

def main():
    parser = FootballUAParser()
    
    print("=" * 60)
    print("Парсер новостей Football.ua - раздел 'Головне за добу'")
    print("=" * 60)
    
    try:
        news = parser.get_latest_news()
        
        if news:
            print(f"\n📰 Найдено {len(news)} актуальных новостей:")
            print("=" * 60)
            
            for i, article in enumerate(news, 1):
                print(f"{i}. {article['title']}")
                print(f"   🔗 {article['link']}")
                print(f"   📍 Найден через: {article['pattern']}")
                print("-" * 60)
        else:
            print("\n❌ Новости не найдены.")
            print("Возможные причины:")
            print("- Изменилась структура сайта")
            print("- Проблемы с подключением")
            print("- Сайт временно недоступен")
            
    except KeyboardInterrupt:
        print("\n⏹️  Парсинг прерван пользователем")
    except Exception as e:
        print(f"\n💥 Произошла ошибка: {e}")

if __name__ == "__main__":
    main()
        articles.append({"title": title, "link": link})

    return articles

