import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
import random

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация
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
    """Преобразует строку времени в объект datetime с киевским часовым поясом (EEST).
    Поддерживает относительное время (например, '15 minutes ago') и ISO формат."""
    try:
        if not current_time:
            current_time = datetime.now(KIEV_TZ)
        logger.debug(f"Попытка парсинга времени: {time_str}, текущее время: {current_time}")

        # Проверка на относительное время (например, '15 minutes ago')
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

        # Проверка на ISO формат (например, '2025-08-08T18:02:00Z')
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
        return current_time  # Возвращаем текущее время в случае ошибки

def fetch_full_article(url: str) -> tuple[str, str]:
    """Извлекает полный текст и изображение из статьи."""
    try:
        headers = {'User-Agent': random.choice(CONFIG['USER_AGENTS'])}
        logger.info(f"🌐 Загружаем статью: {url}")
        response = requests.get(url, headers=headers, timeout=15)  # Увеличиваем таймаут
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Извлечение текста - РАСШИРЕННАЯ ВЕРСИЯ для AI
        content_selectors = [
            # Селекторы специально для OneFootball
            '[data-testid="article-body"]',
            '.ArticleBody',
            '.article-body',
            '.article-content',
            '.post-content', 
            '[class*="body"]',
            '[class*="content"]',
            'article',
            '.main-text',
            '.content'
        ]
        
        article_text = ""
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                logger.info(f"📄 Найден контент с селектором: {selector}")
                
                # Убираем ненужные элементы
                for unwanted in content_div.find_all(['script', 'style', 'iframe', 'div[class*="ad"]', 'aside', 'nav']):
                    unwanted.decompose()
                
                # Извлекаем все параграфы
                paragraphs = content_div.find_all('p')
                if paragraphs:
                    meaningful_paragraphs = []
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        if len(text) > 20:  # Только содержательные параграфы
                            meaningful_paragraphs.append(text)
                    
                    if meaningful_paragraphs:
                        article_text = '\n'.join(meaningful_paragraphs)
                        logger.info(f"📝 Извлечено из параграфов: {len(article_text)} символов")
                        break
                else:
                    # Если параграфов нет, берем весь текст
                    article_text = content_div.get_text(strip=True)
                    if len(article_text) > 50:
                        logger.info(f"📝 Извлечен общий текст: {len(article_text)} символов")
                        break
        
        # Если основной контейнер не найден, ищем все параграфы на странице
        if not article_text or len(article_text) < 100:
            logger.warning("📄 Основной контент не найден, ищем параграфы по всей странице")
            all_paragraphs = soup.find_all('p')
            meaningful_paragraphs = []
            
            for p in all_paragraphs:
                text = p.get_text(strip=True)
                # Фильтруем содержательные параграфы
                if (len(text) > 50 and 
                    not any(skip in text.lower() for skip in [
                        'cookie', 'advertisement', 'subscribe', 'follow', 'social', 
                        'newsletter', 'privacy', 'terms', 'copyright', '©'
                    ])):
                    meaningful_paragraphs.append(text)
            
            if meaningful_paragraphs:
                article_text = '\n\n'.join(meaningful_paragraphs)
                logger.info(f"📝 Извлечено из всех параграфов: {len(article_text)} символов")
            
            # Если все еще мало контента, расширяем поиск
            if len(article_text) < 200:
                logger.warning("📄 Мало контента, расширяем поиск")
                # Ищем любые текстовые блоки
                text_elements = soup.find_all(['div', 'span'], string=True)
                additional_text = []
                
                for elem in text_elements:
                    text = elem.get_text(strip=True)
                    if (len(text) > 30 and 
                        text not in article_text and
                        not any(skip in text.lower() for skip in ['cookie', 'advertisement', 'menu', 'navigation'])):
                        additional_text.append(text)
                        if len('\n'.join(additional_text)) > 1000:  # Ограничиваем объем
                            break
                
                if additional_text:
                    if article_text:
                        article_text += '\n\n' + '\n'.join(additional_text)
                    else:
                        article_text = '\n'.join(additional_text)
                    logger.info(f"📝 Добавлен дополнительный контент: {len(article_text)} символов")

        # Очистка текста
        if article_text:
            import re
            # Убираем лишние переносы строк
            article_text = re.sub(r'\n\s*\n\s*\n', '\n\n', article_text)
            # Убираем очень короткие строки (вероятно мусор)
            lines = article_text.split('\n')
            clean_lines = []
            for line in lines:
                line = line.strip()
                if len(line) > 15 or (len(line) > 5 and any(word in line.lower() for word in ['goal', 'match', 'player', 'team', 'football', 'soccer'])):
                    clean_lines.append(line)
            article_text = '\n'.join(clean_lines)
            
            # Ограничиваем размер для AI обработки
            if len(article_text) > 2000:
                sentences = re.split(r'[.!?]+', article_text)
                trimmed_content = ""
                for sentence in sentences:
                    if len(trimmed_content + sentence) < 2000:
                        trimmed_content += sentence + ". "
                    else:
                        break
                article_text = trimmed_content.strip()

        # Извлечение изображения - УЛУЧШЕННАЯ ВЕРСИЯ
        image_selectors = [
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
            '[data-testid="article-image"] img',
            '.article-image img',
            '.featured-image img', 
            '[class*="image"] img',
            'article img:first-of-type',
            '.main-image img',
            '.post-image img',
            'img[src*="onefootball"]',  # Специально для OneFootball
            'img[src*="wp-content"]',   # WordPress изображения
            'figure img',
            '.hero-image img'
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
                    image_url = (img_elem.get('src', '') or 
                               img_elem.get('data-src', '') or 
                               img_elem.get('data-lazy-src', ''))
            
            if image_url:
                # Делаем полный URL если нужно
                if not image_url.startswith('http'):
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/'):
                        image_url = 'https://onefootball.com' + image_url
                
                # Проверяем, что это качественное изображение
                if (not any(small in image_url.lower() for small in ['icon', 'logo', 'thumb', 'avatar', 'placeholder']) 
                    and len(image_url) > 20
                    and ('onefootball' in image_url or 'wp-content' in image_url or 'cloudinary' in image_url)):
                    logger.info(f"🖼️ Найдено изображение: {image_url}")
                    break
                else:
                    image_url = ""  # Сбрасываем если не подходит
        
        logger.info(f"✅ Статья обработана: {len(article_text)} символов текста, {'с изображением' if image_url else 'без изображения'}")
        return article_text, image_url

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки статьи {url}: {e}")
        return "", ""

def translate_and_process_article(title: str, content: str, url: str) -> tuple[str, str]:
    """Переводит и обрабатывает статью с помощью AI"""
    try:
        # Импортируем функции AI обработки
        from ai_processor import create_enhanced_summary, has_gemini_key
        
        if not has_gemini_key():
            logger.warning("AI недоступен - используем базовый перевод")
            return title, content[:200] + "..." if len(content) > 200 else content
        
        logger.info(f"🤖 Переводим и обрабатываем статью: {title[:50]}...")
        
        # Создаем расширенное резюме с переводом
        translated_summary = create_enhanced_summary({
            'title': title,
            'content': content,
            'url': url,
            'source': 'OneFootball'
        })
        
        # Очищаем от возможных markdown символов
        if translated_summary.startswith('**') and translated_summary.endswith('**'):
            translated_summary = translated_summary.strip('* ').strip()
        
        # Убираем markdown из контента тоже
        if content:
            content = content.replace('**', '')
        
        logger.info(f"✅ Статья обработана AI: {len(translated_summary)} символов")
        return translated_summary, content
        
    except Exception as e:
        logger.error(f"Ошибка AI обработки статьи: {e}")
        return title, content[:200] + "..." if len(content) > 200 else content

def get_latest_news(since_time: datetime = None) -> list:
    """Получает последние новости с OneFootball с фильтрацией по времени и полной обработкой статей."""
    logger.info("Получение новостей с OneFootball...")
    news_items = []

    try:
        headers = {'User-Agent': random.choice(CONFIG['USER_AGENTS'])}
        response = requests.get(CONFIG['BASE_URL'], headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        news_container = soup.select('section article')
        if not news_container:
            logger.warning("Контейнер новостей не найден")
            return []

        current_time = datetime.now(KIEV_TZ)
        # Определение since_time по умолчанию
        if since_time is None:
            current_hour = current_time.hour
            current_minute = current_time.minute
            # Диапазон 5:50 - 6:10 утра
            if 5 <= current_hour < 6 and current_minute >= 50 or current_hour == 6 and current_minute <= 10:
                since_time = current_time.replace(hour=1, minute=0, second=0, microsecond=0)
                logger.info(f"Режим 5 часов: since_time установлено на {since_time}")
            else:
                since_time = current_time - timedelta(minutes=20)
                logger.info(f"Режим 20 минут: since_time установлено на {since_time}")

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
                if not time_str:  # Если datetime отсутствует, попробуем извлечь из текста
                    time_text = time_elem.get_text(strip=True) if time_elem else ''
                    time_str = time_text if time_text else str(current_time)
                logger.debug(f"Извлечено время новости: {time_str}")

                publish_time = parse_publish_time(time_str, current_time)

                if publish_time < since_time:
                    logger.info(f"Новость '{title[:50]}...' старая, пропускаем (publish_time={publish_time}, since_time={since_time})")
                    continue

                # Получаем полный текст статьи и изображение
                logger.info(f"📖 Загружаем полный контент статьи: {url}")
                article_text, image_url = fetch_full_article(url)
                
                logger.info(f"📄 Получено {len(article_text)} символов контента")
                
                # Если нет изображения из статьи, пытаемся взять thumbnail
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
                            logger.info(f"🖼️ Используем thumbnail: {image_url}")

                # КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Используем AI для перевода и обработки
                logger.info(f"🤖 Переводим и обрабатываем с AI...")
                translated_title, processed_content = translate_and_process_article(title, article_text, url)

                # Создаем summary из обработанного контента
                summary = processed_content[:300] + "..." if len(processed_content) > 300 else processed_content

                news_item = {
                    'title': translated_title,
                    'url': url,
                    'content': article_text,  # ОРИГИНАЛЬНЫЙ полный контент для дальнейшей AI обработки
                    'summary': summary,       # Краткое резюме
                    'publish_time': publish_time,
                    'image_url': image_url,
                    'source': 'OneFootball',
                    # Дополнительные поля для отладки
                    'original_title': title,
                    'original_content': article_text,
                    'processed_content': processed_content  # Обработанный AI контент
                }
                news_items.append(news_item)
                logger.info(f"Добавлена новость: {translated_title[:50]}...")
                
                # Небольшая пауза между обработкой статей
                import time
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Ошибка обработки новости: {e}")
                continue

        logger.info(f"Найдено {len(news_items)} новых новостей с OneFootball")
        return news_items

    except Exception as e:
        logger.error(f"Ошибка получения новостей с OneFootball: {e}")
        return []
