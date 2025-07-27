
import requests
from bs4 import BeautifulSoup

def get_latest_news():
    url = "https://football.ua/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/114.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    articles = []
    # Ищем блок с новостями
    news_section = soup.find('section', {'class': 'main-news-feed'})
    if not news_section:
        print("Не найден блок новостей")
        return []

    # Ищем все ссылки в этом блоке
    news_links = news_section.find_all('a', {'class': 'main-news-feed__link'})[:5]

    for tag in news_links:
        title = tag.get_text(strip=True)
        link = tag['href']
        if not link.startswith('http'):
            link = 'https://football.ua' + link
        articles.append({"title": title, "link": link})

    return articles

