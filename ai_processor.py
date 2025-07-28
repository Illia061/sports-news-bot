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

def clean_text(text: str) -> str:
    """Очищает текст от лишних символов, включая разбитый формат"""
    if not text or not isinstance(text, str):
        return ""
    
    # Удаляем разбитый текст (например, И. н. ш. е.)
    text = re.sub(r'(\w)\.\s*', r'\1', text)  # Удаляем точки между символами
    text = re.sub(r'\s*\.\s*', ' ', text)     # Удаляем лишние точки
    text = re.sub(r'\s+', ' ', text).strip()  # Удаляем лишние пробелы
    # Удаляем непечатные символы, сохраняя кириллицу
    text = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ0-9.,!?:;\-]', '', text)
    return text

def clean_intro(text: str) -> str:
    """Очищает текст от служебной информации"""
    if not text or not isinstance(text, str):
        return ""
    
    text = text.strip()
    
    # Проверяем, не разбит ли текст на символы
    if len(text) > 50 and text.count('. ') > len(text) // 10:
        print("⚠️  Обнаружен текст, разбитый на символы - применяем очистку")
        text = clean_text(text)
    
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
        return clean_text(article_data.get('summary', '') or article_data.get('title', ''))
    
    try:
        title = article_data.get('title', '')
        content = article_data.get('content', '')
        summary = article_data.get('summary', '')
        
        # Используем контент или готовую выжимку
        text_to_process = content if content else summary if summary else title
        text_to_process = clean_text(text_to_process)  # Очищаем перед отправкой в OpenAI
        
        print(f"🤖 Создаем AI резюме для: {title[:50]}...")
        print(f"📝 Исходный текст (первые 200 символов): {repr(text_to_process[:200])}")
        
        # Упрощенный и более точный промпт
        prompt = f"""Створи коротке резюме для статті про футбол українською мовою.

Вимоги:
- Пиши природною українською мовою, уникай розбиття слів на окремі символи.
- Збережи всі імена, цифри та позиції в рейтингах (наприклад, "Топ-10").
- Якщо стаття містить рейтинг або список, включи його повністю.
- Максимум 3-4 речення, плюс повний рейтинг, якщо він є.
- Уникай додавання крапок між символами (наприклад, "І. н. ш. е.").

Заголовок: {title}

Текст статті:
{text_to_process[:1000]}  # Ограничиваем для экономии токенов

Резюме українською:"""

        print("🔄 Отправляем запрос в OpenAI...")
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": """Ти експерт зі створення коротких резюме футбольних новин українською мовою.
Важливо: Пиши природною українською, не розбивай слова на окремі символи. Зберігай усі рейтинги та списки повністю."""
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            max_tokens=600,
            temperature=0.3,  # Збільшуємо температуру для кращої якості
            top_p=0.9,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )
        
        enhanced_summary = response.choices[0].message.content.strip()
        enhanced_summary = clean_text(enhanced_summary)  # Очищаем результат
        
        print(f"🔍 AI ответ (первые 200 символов): {repr(enhanced_summary[:200])}")
        print(f"📊 Длина ответа: {len(enhanced_summary)} символов")
        
        # Проверка на разбитый текст
        char_count = sum(1 for c in enhanced_summary if c == '.')
        total_chars = len(enhanced_summary)
        
        if total_chars > 100 and char_count > total_chars / 20:
            print("❌ ОБНАРУЖЕН РАЗБИТЫЙ ТЕКСТ! Используем fallback...")
            # Fallback: берем первые 2-3 предложения из контента
            sentences = [s.strip() for s in text_to_process.split('. ') if s.strip()]
            result = '. '.join(sentences[:2]) + '.'
            # Добавляем рейтинг, если є
            if 'Топ-' in text_to_process:
                lines = text_to_process.split('\n')
                rating_lines = [line for line in lines if line.strip() and ('Топ-' in line or line[0].isdigit())]
                if rating_lines:
                    result += '\n\n' + '\n'.join(rating_lines)
            return clean_text(result)
        
        print(f"✅ AI резюме создано успешно")
        return enhanced_summary
        
    except Exception as e:
        print(f"❌ Помилка при створенні покращеного резюме: {e}")
        import traceback
        traceback.print_exc()
        # Fallback: чистим исходный текст
        return clean_text(article_data.get('summary', '') or article_data.get('title', ''))

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
            final_summary = create_enhanced_summary(article_data)
        else:
            print("📝 Используем базовое резюме...")
            final_summary = clean_text(summary or content[:200])

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
