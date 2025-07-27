
import requests
from bs4 import BeautifulSoup

def get_latest_news():
    url = "https://football.ua/"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    articles = []
    # Обновленный селектор для "Головне за добу" — это блок с классом 'main-news-feed__item'
    # Но лучше взять новости из раздела 'top-news' или похожих, смотря на html
    
    # Пример: новости в блоке с классом "top-news" и теги 'a' внутри
    news_section = soup.find('div', class_='main-news-feed')
    if not news_section:
        print("Не найден блок новостей")
        return []

    news_blocks = news_section.select('a.main-news-feed__link')[:5]

    for tag in news_blocks:
        title = tag.get_text(strip=True)
        link = tag['href']
        if not link.startswith('http'):
            link = 'https://football.ua' + link
        articles.append({"title": title, "link": link})

    return articles

