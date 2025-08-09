
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
import random
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG = {
    'USER_AGENTS': [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0'
    ],
    'BASE_URL': 'https://onefootball.com/en/home',
    'MAX_NEWS': 10
}

KIEV_TZ = ZoneInfo("Europe/Kiev")

def parse_publish_time(time_str: str, current_time: datetime = None) -> datetime:
    """Преобразует строку времени в объект datetime с киевским часовым поясом."""
    try:
        if not current_time:
            current_time = datetime.now(KIEV_TZ)
        logger.debug(f"Попытка парсинга времени: {time_str}, текущее время: {current_time}")

        if 'ago' in time_str.lower():
            for unit in ['minutes', 'hours', 'days']:
                if unit in time_str.lower():
                    value = int(''.join(filter(str.isdigit, time_str)))
                    if unit == 'minutes':
                        delta = timedelta(minutes=value)
                    elif unit == 'hours':
                        delta = timedelta(hours=value)
                    elif unit == 'days':
                        delta = timedelta(days=value)
                    return current_time - delta
            raise ValueError("Не удалось распознать относительное время")

        if 'T' in time_str:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00')).astimezone(KIEV_TZ)
        else:
            try:
                dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M %Z').astimezone(KIEV_TZ)
            except ValueError:
                dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M').replace(tzinfo=KIEV_TZ)
        logger.debug(f"Успешно распарсено время: {time_str} -> {dt}")
        return dt
    except Exception as e:
        logger.warning(f"Ошибка парсинга времени '{time_str}': {e}")
        return current_time

async def fetch_full_article(url: str) -> tuple[str, str]:
    """Извлекает полный текст и изображение из статьи асинхронно."""
    try:
        headers = {'User-Agent': random.choice(CONFIG['USER_AGENTS'])}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as response:
                response.raise_for_status()
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')

                content_selectors = [
                    '.article-content',
                    '.post-content', 
                    '[class*="body"]',
                    'article',
                    '.main-text',
                    '.content'
                ]
                
                article_text = ""
                for selector in content_selectors:
                    content_div = soup.select_one(selector)
                    if content_div:
                        for unwanted in content_div.find_all(['script', 'style', 'iframe', 'div[class*="ad"]']):
                            unwanted.decompose()
                        
                        paragraphs = content_div.find_all('p')
                        if paragraphs:
                            article_text = '\n'.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])
                            break
                        else:
                            article_text = content_div.get_text(strip=True)
                            break
                
                if not article_text:
                    all_paragraphs = soup.find_all('p')
                    meaningful_paragraphs = []
                    for p in all_paragraphs:
                        text = p.get_text(strip=True)
                        if (len(text) > 30 and 
                            not any(skip in text.lower() for skip in ['cookie', 'advertisement', 'subscribe', 'photo', 'source'])):
                            meaningful_paragraphs.append(text)
                    
                    article_text = '\n'.join(meaningful_paragraphs)
                    if len(article_text) > 1500:
                        sentences = re.split(r'[.!?]+', article_text)
                        trimmed_content = ""
                        for sentence in sentences:
                            if len(trimmed_content + sentence) < 1500:
                                trimmed_content += sentence + ". "
                            else:
                                break
                        article_text = trimmed_content.strip()

                image_selectors = [
                    'meta[property="og:image"]',
                    '.article-image img',
                    '.featured-image img', 
                    '[class*="image"] img',
                    'article img:first-of-type',
                    '.main-image img',
                    '.post-image img',
                    'img[src*="onefootball"]'
                ]
                
                image_url = ""
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
                        if not image_url.startswith('http'):
                            if image_url.startswith('//'):
                                image_url = 'https:' + image_url
                            elif image_url.startswith('/'):
                                image_url = 'https://onefootball.com' + image_url
                        if not any(small in image_url.lower() for small in ['icon', 'logo', 'thumb', 'avatar']) and len(image_url) > 20:
                            logger.debug(f"Найдено изображение: {image_url}")
                            break
                
                logger.info(f"Извлечено {len(article_text)} символов текста и {'изображение' if image_url else 'без изображения'}")
                return article_text, image_url

    except aiohttp.ClientTimeout:
        logger.error(f"Таймаут при загрузке статьи {url}")
        return "", ""
    except aiohttp.ClientResponseError as e:
        logger.error(f"HTTP ошибка при загрузке статьи {url}: {e}")
        return "", ""
    except aiohttp.ClientError as e:
        logger.error(f"Ошибка запроса при загрузке статьи {url}: {e}")
        return "", ""
    except Exception as e:
        logger.error(f"Неизвестная ошибка при загрузке статьи {url}: {e}", exc_info=True)
        return "", ""

def clean_text_for_ai(text: str) -> str:
    """Очищает текст для AI-анализа."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s*#\w+\s*', ' ', text)
    text = re.sub(r'[⚽🏆🥅📰📊🔥💪👑🎯⭐🚫✅❌🌍]', '', text)
    text = re.sub(r'(ESPN Soccer|Football\.ua|OneFootball)', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.replace('**', '')
    return text

def translate_and_process_article(title: str, content: str, url: str) -> tuple[str, str]:
    """Переводит и обрабатывает статью с помощью AI."""
    try:
        from ai_processor import create_enhanced_summary, has_gemini_key
        
        if not has_gemini_key():
            logger.warning("AI недоступен - используем базовый перевод")
            return title, content[:200] + "..." if len(content) > 200 else content
        
        logger.info(f"🤖 Переводим и обрабатываем статью: {title[:50]}...")
        
        translated_summary = create_enhanced_summary({
            'title': title,
            'content': content,
            'url': url,
            'source': 'OneFootball'
        })
        
        translated_summary = clean_text_for_ai(translated_summary)
        content = clean_text_for_ai(content)
        
        logger.info(f"✅ Статья обработана AI: {len(translated_summary)} символов")
        return translated_summary, content
        
    except Exception as e:
        logger.error(f"Ошибка AI обработки статьи: {e}")
        return title, content[:200] + "..." if len(content) > 200 else content

async def get_latest_news(since_time: datetime = None) -> list:
    """Получает последние новости с OneFootball с фильтрацией по времени."""
    logger.info("Получение новостей с OneFootball...")
    news_items = []

    try:
        headers = {'User-Agent': random.choice(CONFIG['USER_AGENTS'])}
        async with aiohttp.ClientSession() as session:
            async with session.get(CONFIG['BASE_URL'], headers=headers, timeout=10) as response:
                response.raise_for_status()
                soup = BeautifulSoup(await response.text(), 'html.parser')

        news_container = soup.select('section article')
        if not news_container:
            logger.warning("Контейнер новостей не найден")
            return []

        current_time = datetime.now(KIEV_TZ)
        if since_time is None:
            current_hour = current_time.hour
            current_minute = current_time.minute
            if 5 <= current_hour < 6 and current_minute >= 50 or current_hour == 6 and current_minute <= 10:
                since_time = current_time.replace(hour=1, minute=0, second=0, microsecond=0)
                logger.info(f"Режим 5 часов: since_time установлено на {since_time}")
            else:
                since_time = current_time - timedelta(minutes=20)
                logger.info(f"Режим 20 минут: since_time установлено на {since_time}")

        tasks = []
        articles_data = []
        for article in news_container[:CONFIG['MAX_NEWS']]:
            try:
                title_elem = article.select_one('h3, [class*="title"]')
                title = title_elem.get_text(strip=True) if title_elem else ''

                link_elem = article.select_one('a[href]')
                url = link_elem['href'] if link_elem else ''
                if url and not url.startswith('http'):
                    url = 'https://onefootball.com' + url

                time_elem = article.select_one('time, [class*="date"]')
                time_str = time_elem['datetime'] if time_elem and 'datetime' in time_elem.attrs else ''
                if not time_str:
                    time_text = time_elem.get_text(strip=True) if time_elem else ''
                    time_str = time_text if time_text else str(current_time)
                logger.debug(f"Извлечено время новости: {time_str}")

                publish_time = parse_publish_time(time_str, current_time)

                if publish_time < since_time:
                    logger.info(f"Новость '{title[:50]}...' старая, пропускаем")
                    continue

                articles_data.append((title, url, publish_time))
                tasks.append(fetch_full_article(url))
            except Exception as e:
                logger.error(f"Ошибка обработки новости: {e}")
                continue

        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for (title, url, publish_time), result in zip(articles_data, results):
            try:
                if isinstance(result, Exception):
                    logger.error(f"Ошибка загрузки статьи {url}: {result}")
                    continue
                
                article_text, image_url = result
                if not image_url:
                    thumb_img = article.select_one('img')
                    if thumb_img:
                        thumb_url = thumb_img.get('src', '') or thumb_img.get('data-src', '')
                        if thumb_url:
                            if not thumb_url.startswith('http'):
                                if thumb_url.startswith('//'):
                                    thumb_url = 'https:' + thumb_url
                                elif thumb_url.startswith('/'):
                                    thumb_url = 'https://onefootball.com' + thumb_url
                            image_url = thumb_url

                translated_title, processed_content = translate_and_process_article(title, article_text, url)

                news_item = {
                    'title': translated_title,
                    'url': url,
                    'content': processed_content,
                    'summary': processed_content[:300] + "..." if len(processed_content) > 300 else processed_content,
                    'publish_time': publish_time,
                    'image_url': image_url,
                    'source': 'OneFootball',
                    'original_title': title,
                    'original_content': article_text
                }
                news_items.append(news_item)
                logger.info(f"Добавлена новость: {translated_title[:50]}...")
            except Exception as e:
                logger.error(f"Ошибка обработки статьи {url}: {e}")
                continue

        logger.info(f"Найдено {len(news_items)} новых новостей с OneFootball")
        return news_items

    except aiohttp.ClientTimeout:
        logger.error("Таймаут при загрузке страницы OneFootball")
        return []
    except aiohttp.ClientResponseError as e:
        logger.error(f"HTTP ошибка при загрузке страницы OneFootball: {e}")
        return []
    except aiohttp.ClientError as e:
        logger.error(f"Ошибка запроса при загрузке страницы OneFootball: {e}")
        return []
    except Exception as e:
        logger.error(f"Неизвестная ошибка получения новостей с OneFootball: {e}")
        return []
