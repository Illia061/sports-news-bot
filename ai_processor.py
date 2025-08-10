import os
import re
import requests
from datetime import datetime
from typing import Optional

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Инициализация Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_AVAILABLE = False
if genai and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        GEMINI_AVAILABLE = True
    except Exception as e:
        print(f"[AI Processor] Ошибка инициализации Gemini: {e}")
        GEMINI_AVAILABLE = False


def clean_text(text: str) -> str:
    """Удаляет лишние пробелы, переносы строк и HTML-теги."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def summarize_text(text: str) -> str:
    """Создает краткое резюме текста с помощью Gemini, если доступно."""
    text = clean_text(text)
    if not text:
        return ""

    if GEMINI_AVAILABLE:
        try:
            prompt = (
                "Сделай короткий, информативный и связный пересказ этого текста для новостного поста. "
                "Без приветствий, оценочных суждений и лишних деталей. "
                f"Текст: {text}"
            )
            response = model.generate_content(prompt)
            if response and hasattr(response, "text"):
                return clean_text(response.text)
        except Exception as e:
            print(f"[AI Processor] Ошибка генерации резюме: {e}")

    # fallback — обрезаем до 500 символов
    return (text[:497] + "...") if len(text) > 500 else text


def format_for_social_media(title: str, content: str, source: Optional[str] = None) -> str:
    """
    Форматирует новость в единый стиль:
    - Жирный заголовок
    - Ниже текст поста
    - Без упоминаний источников и хэштегов
    """
    title = clean_text(title)
    ai_summary = summarize_text(content)
    post = f"<b>{title}</b>\n\n{ai_summary}"
    return post


def download_image(url: str, save_path: str) -> Optional[str]:
    """Скачивает изображение по URL."""
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(r.content)
            return save_path
    except Exception as e:
        print(f"[AI Processor] Ошибка скачивания изображения: {e}")
    return None

