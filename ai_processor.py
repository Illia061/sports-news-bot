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
    """Очищает текст от служебной информации"""
    if not text or not isinstance(text, str):
        return ""
    
    text = text.strip()
    
    # Проверяем, не разбит ли текст на символы (как в вашем примере)
    if len(text) > 50 and text.count('. ') > len(text) // 10:
        # Если много точек с пробелами - возможно, текст разбит на символы
        print("⚠️  Обнаружен текст, разбитый на символы - пропускаем очистку")
        return text

    # Удалить даты в начале
    text = re.sub(r"^(Сьогодні|Вчора)(,)?\s+\d{1,2}\s+\w+\s+\d{4}", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\d{1,2}\s+\w+\s+\d{4},\s*\d{1,2}:\d{2}", "", text)

    # Удалить категории
    text = re.sub(r"^([А-ЯІЇЄҐа-яіїєґ\s]+) –(\s[А-Яа-я\s]+)? – ", "", text)
    text = re.sub(r"^([А-ЯІЇЄҐа-яіїєґ\s]+) – ", "", text)

    return text.strip()
    
def create_enhanced_summary(article_data: Dict[str, Any]) -> str:
    """Создает улучшенное резюме новости на основе полных данных статьи"""
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
        
        print(f"🤖 Создаем AI резюме для: {title[:50]}...")
        print(f"📝 Обрабатываем текст длиной: {len(text_to_process)} символов")
        
        # Улучшенный промпт с акцентом на рейтинги
        prompt = f"""Створи стислий виклад цієї футбольної новини українською мовою.

ВАЖЛИВО:
- Якщо в статті є рейтинг або список (топ-10, топ-5) - ОБОВ'ЯЗКОВО включи його повністю
- Зберігай всі числа, позиції та імена з рейтингів
- Пиши природною українською мовою
- Не розбивай текст на окремі символи
- Максимум 3-4 речення + повний рейтинг якщо є

Заголовок: {title}

Повний текст новини:
{text_to_process}

Створи стислий виклад:"""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": """Ти - експерт зі створення стислих викладів футбольних новин українською мовою.
ГОЛОВНЕ ПРАВИЛО: Якщо в новині є рейтинг, топ-список або нумерований список - ОБОВ'ЯЗКОВО включай його повністю.
Пиши природною українською мовою, не розбивай слова на символи."""
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            max_tokens=500,
            temperature=0.3  # Зменшили температуру для более стабильного вывода
        )
        
        enhanced_summary = response.choices[0].message.content.strip()
        
        # Проверяем, не получили ли мы "разбитый" текст
        if len(enhanced_summary) > 50 and enhanced_summary.count('. ') > len(enhanced_summary) // 10:
            print("⚠️  AI вернул разбитый текст, используем оригинальный")
            return text_to_process[:300] + "..." if len(text_to_process) > 300 else text_to_process
        
        print(f"✅ AI резюме создано: {len(enhanced_summary)} символов")
        return enhanced_summary
        
    except Exception as e:
        print(f"❌ Помилка при створенні покращеного резюме: {e}")
        # Возвращаем оригинальный текст без обработки
        content = article_data.get('content', '')
        if content:
            return content[:300] + "..." if len(content) > 300 else content
        return article_data.get('summary', '') or article_data.get('title', '')

def format_for_social_media(article_data: Dict[str, Any]) -> str:
    """Форматирует новость для публикации в социальных сетях"""
    try:
        title = article_data.get('title', '')
        summary = article_data.get('summary', '')
        content = article_data.get('content', '')
        
        print(f"📱 Форматируем для соцсетей: {title[:50]}...")

        # Используем AI или базовое резюме
        if has_openai_key():
            print("🤖 Используем AI для создания резюме...")
            ai_summary = create_enhanced_summary(article_data)
            # НЕ применяем clean_intro к AI резюме, так как оно уже обработано
            final_summary = ai_summary
        else:
            print("📝 Используем базовое резюме...")
            final_summary = clean_intro(summary or content[:200])

        # Форматируем пост
        post = f"<b>⚽ {title}</b>\n\n"

        if final_summary and final_summary != title and len(final_summary.strip()) > 10:
            post += f"{final_summary}\n\n"

        # Добавляем хештеги
        post += "#футбол #новини #спорт"
        
        print(f"✅ Пост отформатирован: {len(post)} символов")
        return post

    except Exception as e:
        print(f"❌ Помилка форматування: {e}")
        return f"<b>⚽ {article_data.get('title', '')}</b>\n\n#футбол #новини"

def download_image(image_url: str, filename: str = None) -> str:
    """Загружает изображение и возвращает путь к файлу"""
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
    """Полная обработка статьи для публикации"""
    try:
        print(f"🔄 Обрабатываем статью: {article_data.get('title', '')[:50]}...")
        
        # Создаем текст поста
        post_text = format_for_social_media(article_data)
        
        # Загружаем изображение если есть
        image_path = ""
        if article_data.get('image_url'):
            print(f"🖼️  Загружаем изображение: {article_data['image_url'][:50]}...")
            image_path = download_image(article_data['image_url'])
        
        result = {
            'title': article_data.get('title', ''),
            'post_text': post_text,
            'image_path': image_path,
            'image_url': article_data.get('image_url', ''),
            'url': article_data.get('url', ''),
            'summary': article_data.get('summary', ''),
            'ai_used': has_openai_key()
        }
        
        print(f"✅ Статья обработана: AI={'Да' if has_openai_key() else 'Нет'}")
        return result
        
    except Exception as e:
        print(f"❌ Помилка обробки статті: {e}")
        return {
            'title': article_data.get('title', ''),
            'post_text': f"⚽ {article_data.get('title', '')}\n\n#футбол #новини",
            'image_path': '',
            'image_url': '',
            'url': article_data.get('url', ''),
            'summary': article_data.get('summary', ''),
            'ai_used': False
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

if __name__ == "__main__":
    # Простая проверка наличия OpenAI ключа
    if has_openai_key():
        print("✅ OpenAI API ключ найден - AI функции доступны")
    else:
        print("⚠️  OpenAI API ключ не найден - используются базовые функции")
