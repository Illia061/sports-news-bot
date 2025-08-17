import re
import os
import requests
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import google.generativeai as genai

from db import cursor

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_AVAILABLE = False
model = None

def init_gemini():
    global GEMINI_AVAILABLE, model
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY не найден - используем базовую проверку дубликатов")
        return
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        GEMINI_AVAILABLE = True
        print("✅ Gemini инициализирован для проверки дубликатов")
    except Exception as e:
        print(f"❌ Ошибка инициализации Gemini: {e}")

def has_gemini_key() -> bool:
    if not GEMINI_AVAILABLE:
        init_gemini()
    return GEMINI_AVAILABLE

class AIContentSimilarityChecker:
    def __init__(self, similarity_threshold: float = 0.7):
        self.similarity_threshold = similarity_threshold
        if not has_gemini_key():
            print("⚠️ AI недоступен - будет использована базовая проверка")

    def clean_text_for_ai(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s*#\w+\s*', ' ', text)
        text = re.sub(r'[⚽🏆🥅📰📊🔥💪👑🎯⭐🚫✅❌🌍]', '', text)
        text = re.sub(r'(ESPN Soccer|Football\.ua|OneFootball)', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def ai_compare_texts(self, new_text: str, existing_texts: List[str]) -> Dict[str, Any]:
        if not has_gemini_key() or not model:
            return {"ai_available": False, "similarities": [], "is_duplicate": False}
        return {"ai_available": False, "similarities": [], "is_duplicate": False}

    def fallback_similarity_check(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0
        words1 = set(self.clean_text_for_ai(text1).lower().split())
        words2 = set(self.clean_text_for_ai(text2).lower().split())
        stop_words = {'в','на','за','до','від','для','про','під','над','при','з','у','і','та','або','але'}
        words1 = {w for w in words1 if len(w) > 2 and w not in stop_words}
        words2 = {w for w in words2 if len(w) > 2 and w not in stop_words}
        if not words1 or not words2:
            return 0.0
        common_words = words1.intersection(words2)
        similarity = len(common_words) / max(len(words1), len(words2))
        return similarity

class TelegramChannelChecker:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
    def get_recent_posts(self, limit: int = 5, since_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        return []

def get_recent_posts_from_db(limit: int = 10, since_time: Optional[datetime] = None):
    query = "SELECT title, post_text, posted_at FROM posted_news ORDER BY posted_at DESC LIMIT ?"
    cursor.execute(query, (limit,))
    rows = cursor.fetchall()
    posts = []
    for row in rows:
        title, post_text, posted_at = row
        text = post_text or title
        if text:
            try:
                dt = datetime.fromisoformat(posted_at)
            except Exception:
                dt = None
            if not since_time or (dt and dt >= since_time):
                posts.append({'text': text, 'date': dt})
    print(f"✅ Получено {len(posts)} последних постов из базы")
    return posts

def check_content_similarity(new_article: Dict[str, Any], threshold: float = 0.7, since_time: Optional[datetime] = None) -> bool:
    print(f"🔍 AI проверка дубликатов: {new_article.get('title', '')[:50]}...")
    ai_checker = AIContentSimilarityChecker(threshold)
    channel_checker = TelegramChannelChecker()
    new_text = new_article.get('post_text') or new_article.get('title', '')
    if not new_text:
        return False
    db_posts = get_recent_posts_from_db(limit=20, since_time=since_time)
    channel_posts = channel_checker.get_recent_posts(limit=10, since_time=since_time)
    recent_posts = db_posts + channel_posts
    if not recent_posts:
        return False
    existing_texts = [post['text'] for post in recent_posts]
    for existing_text in existing_texts:
        similarity = ai_checker.fallback_similarity_check(new_text, existing_text)
        if similarity >= threshold:
            return True
    return False
