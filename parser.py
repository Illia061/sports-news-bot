
import requests
from bs4 import BeautifulSoup

def get_latest_news():
    url = "https://football.ua/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        articles = []
        
        # Ищем блок с новостями разными способами
        news_section = None
        
        # Способ 1: основной блок новостей
        news_section = soup.find('section', class_='main-news-feed')
        if not news_section:
            news_section = soup.find('div', class_='main-news-feed')
        
        # Способ 2: если не найден, ищем по другим классам
        if not news_section:
            possible_classes = ['main-news', 'news-main', 'main-content', 'news-list']
            for class_name in possible_classes:
                news_section = soup.find(['section', 'div'], class_=class_name)
                if news_section:
                    break
        
        # Способ 3: если все еще не найден, используем всю страницу
        if not news_section:
            news_section = soup
        
        # Ищем ссылки на новости
        news_links = []
        
        # Пробуем разные селекторы для ссылок
        link_selectors = [
            'a.main-news-feed__link',
            'a[href*="/news/"]',
            'a[href*="/ukraine/"]'
        ]
        
        for selector in link_selectors:
            links = news_section.select(selector)
            if links:
                news_links = links[:5]
                break
        
        # Если ссылки не найдены, ищем все ссылки с новостями
        if not news_links:
            all_links = news_section.find_all('a', href=True)
            news_links = []
            for link in all_links:
                href = link.get('href', '')
                if '/news/' in href or '/ukraine/' in href:
                    news_links.append(link)
                if len(news_links) >= 5:
                    break
        
        # Обрабатываем найденные ссылки
        for tag in news_links:
            title = tag.get_text(strip=True)
            link = tag.get('href', '')
            
            if not title or not link:
                continue
            
            # Формируем полную ссылку
            if link.startswith('/'):
                link = 'https://football.ua' + link
            elif not link.startswith('http'):
                link = 'https://football.ua/' + link
            
            # Добавляем статью если заголовок не пустой
            if len(title) > 5:
                articles.append({"title": title, "link": link})
        
        return articles
        
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

# Тестовая функция
def test_parser():
    print("Тестируем парсер...")
    news = get_latest_news()
    
    if news:
        print(f"Найдено {len(news)} новостей:")
        for i, article in enumerate(news, 1):
            print(f"{i}. {article['title']}")
            print(f"   {article['link']}")
            print()
    else:
        print("Новости не найдены")

if __name__ == "__main__":
    test_parser()
