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
        print(f"📝 Исходный текст (первые 200 символов): {repr(text_to_process[:200])}")
        
        # Попробуем английский промпт - возможно проблема в украинском тексте промпта
        prompt = f"""Please create a brief summary of this Ukrainian football news article.

REQUIREMENTS:
- Write the summary in Ukrainian language
- If the article contains a rating/top list (like "Топ-10"), include it completely with all positions
- Keep all names, numbers, and positions from rankings
- Write naturally in Ukrainian, don't break words into separate characters
- Maximum 3-4 sentences plus the complete ranking if present

Title: {title}

Article content:
{text_to_process}

Please provide the summary in Ukrainian:"""

        print("🔄 Отправляем запрос в OpenAI...")
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": """You are an expert at creating brief summaries of football news in Ukrainian language.
IMPORTANT: If the news contains any rating, top list, or numbered list - you MUST include it completely.
Always write in natural Ukrainian language. Never break words into separate characters."""
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            max_tokens=600,
            temperature=0.2,  # Еще меньше температуру для стабильности
            top_p=0.9,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )
        
        enhanced_summary = response.choices[0].message.content.strip()
        
        print(f"🔍 AI ответ (первые 200 символов): {repr(enhanced_summary[:200])}")
        print(f"📊 Длина ответа: {len(enhanced_summary)} символов")
        
        # Детальная проверка на "разбитый" текст
        char_count = sum(1 for c in enhanced_summary if c == '.')
        space_count = sum(1 for c in enhanced_summary if c == ' ')
        total_chars = len(enhanced_summary)
        
        print(f"🔍 Анализ текста: точек={char_count}, пробелов={space_count}, всего={total_chars}")
        
        # Если слишком много точек относительно длины - возможно текст разбит
        if total_chars > 100 and char_count > total_chars / 20:
            print("❌ ОБНАРУЖЕН РАЗБИТЫЙ ТЕКСТ!")
            print(f"❌ Проблемный ответ: {enhanced_summary[:300]}")
            
            # Пробуем еще раз с другим промптом
            print("🔄 Пробуем упрощенный промпт...")
            
            simple_prompt = f"""Summarize this Ukrainian football article in Ukrainian. Include any rankings completely.

{title}

{text_to_process[:500]}

Summary in Ukrainian:"""
            
            response2 = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": simple_prompt}
                ],
                max_tokens=400,
                temperature=0.1
            )
            
            enhanced_summary2 = response2.choices[0].message.content.strip()
            print(f"🔍 Второй AI ответ: {repr(enhanced_summary2[:200])}")
            
            # Если и второй ответ плохой, используем fallback
            char_count2 = sum(1 for c in enhanced_summary2 if c == '.')
            if len(enhanced_summary2) > 100 and char_count2 > len(enhanced_summary2) / 20:
                print("❌ И второй ответ разбитый! Используем fallback...")
                # Простая обработка как fallback
                sentences = []
                for line in text_to_process.split('\n'):
                    line = line.strip()
                    if len(line) > 20 and not line.startswith(('Топ-', '1.', '2.')):
                        sentences.append(line)
                    if len(sentences) >= 2:
                        break
                
                result = '. '.join(sentences[:2])
                
                # Добавляем рейтинг
                if 'Топ-' in text_to_process:
                    lines = text_to_process.split('\n')
                    rating_started = False
                    rating_lines = []
                    
                    for line in lines:
                        line = line.strip()
                        if 'Топ-' in line and ':' in line:
                            rating_started = True
                            rating_lines.append(line)
                        elif rating_started and line and (line[0].isdigit() or ';' in line):
                            rating_lines.append(line)
                        elif rating_started and not line:
                            break
                    
                    if rating_lines:
                        result += '\n\n' + '\n'.join(rating_lines)
                
                return result
            else:
                enhanced_summary = enhanced_summary2
        
        print(f"✅ AI резюме создано успешно")
        return enhanced_summary
        
    except Exception as e:
        print(f"❌ Помилка при створенні покращеного резюме: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback обработка
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
