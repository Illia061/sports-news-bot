
import os
import re
from typing import Dict, Any

# Безопасная инициализация OpenAI клиента
client = None
OPENAI_AVAILABLE = False

def init_openai_client():
    """Безопасная инициализация OpenAI клиента"""
    global client, OPENAI_AVAILABLE
    
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("⚠️  OPENAI_API_KEY не найден - AI функции отключены")
            return False
        
        import openai
        client = openai.OpenAI(api_key=api_key)
        OPENAI_AVAILABLE = True
        print("✅ OpenAI клиент инициализирован")
        return True
        
    except ImportError:
        print("⚠️  Библиотека openai не установлена - AI функции отключены")
        return False
    except Exception as e:
        print(f"⚠️  Ошибка инициализации OpenAI: {e} - AI функции отключены")
        return False
        
def clean_intro(text: str) -> str:
    text = text.strip()

    # Удалить фразы типа "Сьогодні, 27 липня 2025" или "Вчора, 26 липня"
    text = re.sub(r"^(Сьогодні|Вчора)(,)?\s+\d{1,2}\s+\w+\s+\d{4}", "", text, flags=re.IGNORECASE)

    # Удалить дату и время в начале (например: "28 липня 2025, 18:39")
    text = re.sub(r"^\d{1,2}\s+\w+\s+\d{4},\s*\d{1,2}:\d{2}", "", text)

    # Удалить фразы с категориями типа "Інше – ", "Італія – Серія А – "
    text = re.sub(r"^([А-ЯІЇЄҐа-яіїєґ\s]+) –(\s[А-Яа-я\s]+)? – ", "", text)
    text = re.sub(r"^([А-ЯІЇЄҐа-яіїєґ\s]+) – ", "", text)

    return text.strip()
    
def create_enhanced_summary(article_data: Dict[str, Any]) -> str:
    """
    Создает улучшенное резюме новости на основе полных данных статьи
    """
    # Инициализируем клиент при первом использовании
    if client is None:
        init_openai_client()
    
    if not OPENAI_AVAILABLE or not client:
        # Возвращаем базовое резюме без AI
        return article_data.get('summary', '') or article_data.get('title', '')
    
    try:
        title = article_data.get('title', '')
        content = article_data.get('content', '')
        summary = article_data.get('summary', '')
        
        # Используем контент или готовую выжимку
        text_to_process = content if content else summary if summary else title
        
        prompt = f""" Ти редактор футбольних новин
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
                    "content": "Ти - експерт зі створення стислих викладів футбольних новин українською мовою. Твоя мета - зробити новину цікавою та зрозумілою. Вимоги: Зрозуміло та цікаво, Збережи всі важливі факти, Якщо у статті є рейтинг - публікуєш його повністю, Якщо у статті є пряма мова - публікуєш стислу вижимку на 3-4 речення
                    "
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            max_tokens=400,
            temperature=0.7
        )
        
        enhanced_summary = response.choices[0].message.content.strip()
        return enhanced_summary
        
    except Exception as e:
        print(f"❌ Помилка при створенні покращеного резюме: {e}")
        # Возвращаем готовую выжимку или заголовок
        return article_data.get('summary', '') or article_data.get('title', '')

def format_for_social_media(article_data: Dict[str, Any]) -> str:
    """
    Форматирует новость для публикации в социальных сетях
    """
    try:
        title = article_data.get('title', '')
        summary = article_data.get('summary', '')

        # Если есть AI резюме, используем его
        if has_openai_key():
            ai_summary = create_enhanced_summary({"title": title, "content": text})
            ai_summary = clean_intro(ai_summary)
        else:
            ai_summary =  clean_intro(summary)

        # Убираем возможные мусорные категории или даты из резюме (простейшая фильтрация)
        unwanted_prefixes = ["Інше", "Італія", "Іспанія", "Німеччина", "Чемпіонат", "Сьогодні", "Вчора"]
        for prefix in unwanted_prefixes:
            if ai_summary.startswith(prefix):
                ai_summary = ai_summary[len(prefix):].strip(": ").lstrip()

        # Форматируем пост с жирным заголовком
        post = f"<b>⚽ {title}</b>\n\n"

        if ai_summary and ai_summary != title:
            post += f"{ai_summary}\n\n"

        # Добавляем хештеги
        post += "#футбол #новини #спорт"

        return post

    except Exception as e:
        print(f"❌ Помилка форматування: {e}")
        return f"<b>⚽ {article_data.get('title', '')}</b>\n\n#футбол #новини"


def download_image(image_url: str, filename: str = None) -> str:
    """
    Загружает изображение и возвращает путь к файлу
    """
    try:
        import requests
        from urllib.parse import urlparse
        import os
        
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
        
        print(f"✅ Изображение сохранено: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"❌ Ошибка загрузки изображения {image_url}: {e}")
        return ""

def process_article_for_posting(article_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Полная обработка статьи для публикации
    """
    try:
        # Создаем текст поста
        post_text = format_for_social_media(article_data)
        
        # Загружаем изображение если есть
        image_path = ""
        if article_data.get('image_url'):
            image_path = download_image(article_data['image_url'])
        
        return {
            'title': article_data.get('title', ''),
            'post_text': post_text,
            'image_path': image_path,
            'image_url': article_data.get('image_url', ''),
            'url': article_data.get('url', ''),
            'summary': article_data.get('summary', '')
        }
        
    except Exception as e:
        print(f"❌ Помилка обробки статті: {e}")
        return {
            'title': article_data.get('title', ''),
            'post_text': f"⚽ {article_data.get('title', '')}\n\n#футбол #новини",
            'image_path': '',
            'image_url': '',
            'url': article_data.get('url', ''),
            'summary': article_data.get('summary', '')
        }

def has_openai_key() -> bool:
    """Проверяет наличие OpenAI API ключа и возможность использования AI"""
    if client is None:
        init_openai_client()
    
    return OPENAI_AVAILABLE and bool(os.getenv("OPENAI_API_KEY"))

# Функции для совместимости со старым кодом
def summarize_news(title: str, url: str) -> str:
    """Обратная совместимость со старым API"""
    article_data = {
        'title': title,
        'url': url,
        'content': '',
        'summary': title
    }
    
    if has_openai_key():
        return create_enhanced_summary(article_data)
    else:
        return f"🔸 {title}"

def simple_summarize(title: str, url: str) -> str:
    """Простое резюме без AI"""
    return f"🔸 {title}"

def test_ai_processor():
    """Тестирование AI процессора"""
    print("🧪 ТЕСТИРОВАНИЕ AI ПРОЦЕССОРА")
    print("=" * 50)
    
    # Проверяем инициализацию
    print("🔧 Инициализация OpenAI...")
    init_openai_client()
    
    test_article = {
        'title': 'Тестова новина про футбол',
        'content': 'Це тестовий контент новини про футбол. Він містить важливу інформацію.',
        'summary': 'Короткий зміст тестової новини',
        'image_url': 'https://example.com/image.jpg',
        'url': 'https://football.ua/test'
    }
    
    print(f"🤖 OpenAI доступен: {'Да' if has_openai_key() else 'Нет'}")
    
    if has_openai_key():
        print("✅ OpenAI API ключ знайдено")
        try:
            summary = create_enhanced_summary(test_article)
            print(f"📝 AI резюме: {summary}")
        except Exception as e:
            print(f"❌ Ошибка AI резюме: {e}")
    else:
        print("⚠️  OpenAI API ключ не знайдено или недоступен")
    
    print("\n📱 Тестируем форматирование поста...")
    post = format_for_social_media(test_article)
    print(f"📱 Пост для соцмереж:\n{post}")
    
    print("\n✅ Тестирование завершено")

if __name__ == "__main__":
    test_ai_processor()
