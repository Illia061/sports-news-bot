
import openai
import requests
from bs4 import BeautifulSoup
import os

# Инициализируем клиент OpenAI
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_article_content(url):
    """Получает содержимое статьи с сайта"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Ищем основной текст статьи
        content_selectors = [
            '.article-content',
            '.post-content', 
            '.news-content',
            '.content',
            'article p',
            '.main-content p'
        ]
        
        content = ""
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                content = " ".join([elem.get_text(strip=True) for elem in elements])
                break
        
        # Если не нашли специфичные селекторы, берем все параграфы
        if not content:
            paragraphs = soup.find_all('p')
            content = " ".join([p.get_text(strip=True) for p in paragraphs[:5]])
        
        return content[:2000] if content else ""  # Ограничиваем длину
        
    except Exception as e:
        print(f"Ошибка при получении контента: {e}")
        return ""

def summarize_news(title, url):
    """Создает краткое содержание новости"""
    try:
        # Получаем содержимое статьи
        article_content = get_article_content(url)
        
        # Если не удалось получить содержимое, используем только заголовок
        if not article_content:
            article_content = title
        
        # Формируем промпт для GPT
        prompt = f"""
Пожалуйста, создай краткое резюме этой футбольной новости на украинском языке.
Резюме должно быть:
- Длиной 2-3 предложения
- Понятным и информативным
- На украинском языке

Заголовок: {title}
Содержание: {article_content}

Краткое резюме:"""

        # Используем новый API OpenAI
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты - помощник, который создает краткие резюме футбольных новостей на украинском языке."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.7
        )
        
        summary = response.choices[0].message.content.strip()
        return summary
        
    except Exception as e:
        print(f"Ошибка при создании резюме: {e}")
        return f"Резюме недоступно. Заголовок: {title}"

def translate_to_ukrainian(text):
    """Переводит текст на украинский язык"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты - переводчик. Переводи текст на украинский язык, сохраняя смысл и стиль."},
                {"role": "user", "content": f"Переведи этот текст на украинский язык:\n\n{text}"}
            ],
            max_tokens=300,
            temperature=0.3
        )
        
        translation = response.choices[0].message.content.strip()
        return translation
        
    except Exception as e:
        print(f"Ошибка при переводе: {e}")
        return text  # Возвращаем оригинальный текст если перевод не удался

# Альтернативная функция без OpenAI (если нет API ключа)
def simple_summarize(title, url):
    """Простое резюме без использования AI"""
    try:
        content = get_article_content(url)
        if content:
            # Берем первые 200 символов как резюме
            summary = content[:200] + "..." if len(content) > 200 else content
            return f"🔸 {summary}"
        else:
            return f"🔸 {title}"
    except:
        return f"🔸 {title}"

# Функция для тестирования
def test_ai_processor():
    """Тестирует работу AI процессора"""
    test_title = "Тестовая новость"
    test_url = "https://football.ua/"
    
    print("Тестируем AI процессор...")
    
    # Проверяем наличие API ключа
    if os.getenv("OPENAI_API_KEY"):
        print("OpenAI API ключ найден, тестируем с AI...")
        summary = summarize_news(test_title, test_url)
        print(f"AI резюме: {summary}")
    else:
        print("OpenAI API ключ не найден, используем простое резюме...")
        summary = simple_summarize(test_title, test_url)
        print(f"Простое резюме: {summary}")

if __name__ == "__main__":
    test_ai_processor()
