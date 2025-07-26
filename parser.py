
import requests
from bs4 import BeautifulSoup

def get_latest_news():
    url = "https://football.ua/"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    articles = []
    for block in soup.select("div.main-news-feed__item")[:5]:
        title_tag = block.select_one("a.main-news-feed__link")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        link = "https://football.ua" + title_tag["href"]
        articles.append({"title": title, "link": link})
    return articles
