import os
import re
from typing import Dict, Any

# OpenAI клиент
client = None

def init_openai_client():
    """Инициализация OpenAI клиента"""
    global client
    
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return False
        
        import openai
        client = openai.OpenAI(api_key=api_key)
        return True
        
    except:
        return False
        
def clean_intro(text: str) -> str:
    """Очистка введения статьи от даты и категорий"""
    text = text.strip()
    
    # Удалить фразы типа "Сьогодні, 27 липня 2025"
    text = re.sub(r"^(Сьогодні|Вчора)(,)?\s+\d{1,2}\s+\w+\s+\d{4}", "", text, flags=re.IGNORECASE)
    
    # Удалить дату и время
    text = re.sub(r"^\d{1,2}\s+\w+\s+\d{4},\s*\d{1,2}:\d{2}", "", text)
    
    # Удалить категории типа "Інше – ", "Італія – Серія А – "
    text = re.sub(r"^([А-ЯІЇЄҐа-яіїєґ\s]+) –(\s[А-Яа-я\s]+)? – ", "", text)
    text = re.sub(r"^([А-ЯІЇЄҐа-яіїєґ\s]+) – ", "", text)
    
    return text.strip()
    
def create_enhanced_summary(article_data: Dict[str, Any]) -> str:
    """Создает AI резюме новости"""
    if client is None:
        init_openai_client()
    
    if not client:
        return article_data.get('summary', '') or article_data.get('title', '')
    
    try:
        title = article_data.get('title', '')
        content = article_data.get('content', '')
        summary = article_data.get('summary', '')
        
        text_to_process = content if content else summary if summary else title
        
        prompt = f"""Ти редактор футбольних новин
Перефразуй і створи інформативний виклад цієї футбольної новини українською мовою.

Вимоги:
- Зрозуміло та цікаво
- Збережи всі важливі факти
- Українською мовою
- Якщо у статті є рейтинг - публікуєш його повністю
- Якщо у статті є пряма мова - публікуєш стислу вижимку на 3-4 речення

Заголовок: {title}
Текст новини: {text_to_process[:1000]}

Стислий виклад:"""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "Ти - експерт зі створення стислих викладів футбольних новин українською мовою."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            max_tokens=400,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
        
    except:
        return article_data.get('summary', '') or article_data.get('title', '')

def download_image(image_url: str, filename: str = None) -> str:
    """Загружает изображение"""
    try:
        import requests
        from urllib.parse import urlparse
        
        if not image_url:
            return ""
        
        # Создаем папку для изображений
        images_dir = "images"
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)
        
        # Определяем имя файла
        if not filename:
            parsed_url = urlparse(image_url)
            filename = os.path.basename(parsed_url.path)
            if not filename or '.' not in filename:
                filename = f"image_{hash(image_url) % 10000}.jpg"
        
        filepath = os.path.join(images_dir, filename)
        
        # Загружаем изображение
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(image_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        return filepath
        
    except:
        return ""

def process_article_for_posting(article_data: Dict[str, Any]) -> Dict[str, Any]:
    """Обработка статьи для публикации"""
    try:
        title = article_data.get('title', '')
        
        # Создаем AI резюме или используем базовое
        ai_summary = create_enhanced_summary(article_data)
        ai_summary = clean_intro(ai_summary)
        
        # Убираем мусорные категории
        unwanted_prefixes = ["Інше", "Італія", "Іспанія", "Німеччина", "Чемпіонат", "Сьогодні", "Вчора"]
        for prefix in unwanted_prefixes:
            if ai_summary.startswith(prefix):
                ai_summary = ai_summary[len(prefix):].strip(": ").lstrip()
        
        # Форматируем пост
        post_text = f"<b>⚽ {title}</b>\n\n"
        if ai_summary and ai_summary != title:
            post_text += f"{ai_summary}\n\n"
        post_text += "#футбол #новини #спорт"
        
        # Загружаем изображение
        image_path = ""
        if article_data.get('image_url'):
            image_path = download_image(article_data['image_url'])
        
        return {
            'title': title,
            'post_text': post_text,
            'image_path': image_path,
            'image_url': article_data.get('image_url', ''),
            'url': article_data.get('url', ''),
            'summary': article_data.get('summary', '')
        }
        
    except:
        return {
            'title': article_data.get('title', ''),
            'post_text': f"⚽ {article_data.get('title', '')}\n\n#футбол #новини",
            'image_path': '',
            'image_url': '',
            'url': article_data.get('url', ''),
            'summary': article_data.get('summary', '')
        }
