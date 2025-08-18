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

        clean_new_text = self.clean_text_for_ai(new_text)
        clean_existing_texts = [self.clean_text_for_ai(text) for text in existing_texts]

        if not clean_new_text or not any(clean_existing_texts):
            return {"ai_available": True, "similarities": [], "is_duplicate": False}

        # Упрощённый промпт (детали опустил для краткости)
        prompt = f"Сравни новость с существующими и определи, дубликат ли она.\nНОВАЯ: {clean_new_text}\nСТАРЫЕ: {clean_existing_texts}"

        try:
            response = model.generate_content(prompt)
            ai_response = response.text.strip()
            is_duplicate = "ТАК" in ai_response.upper() or "YES" in ai_response.upper()
            return {
                "ai_available": True,
                "ai_response": ai_response,
                "similarities": [],
                "is_duplicate": is_duplicate,
            }
        except Exception as e:
            print(f"❌ Ошибка AI анализа: {e}")
            return {"ai_available": False, "error": str(e), "similarities": [], "is_duplicate": False}

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
        return len(common_words) / max(len(words1), len(words2))


class TelegramChannelChecker:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.channel_id = os.getenv('TELEGRAM_CHANNEL_ID')

    def get_recent_posts(self, limit: int = 5, since_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        if not self.bot_token or not self.channel_id:
            return []
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            response = requests.get(url, timeout=30)
            result = response.json()
            if not result.get('ok'):
                return []
            channel_posts = []
            for update in result.get('result', []):
                if 'channel_post' in update:
                    post = update['channel_post']
                    if str(post.get('chat', {}).get('id')) == str(self.channel_id):
                        channel_posts.append(post)
            channel_posts.sort(key=lambda x: x.get('date', 0), reverse=True)
            recent_posts = channel_posts[:limit]
            formatted_posts = []
            for post in recent_posts:
                text = post.get('text') or post.get('caption', '') or ''
                post_date = datetime.fromtimestamp(post.get('date', 0))
                if text and (not since_time or post_date >= since_time):
                    formatted_posts.append({
                        'text': text,
                        'date': post_date,
                        'message_id': post.get('message_id')
                    })
            return formatted_posts
        except Exception:
            return []


def get_recent_posts_from_db():
    query = "SELECT title, post_text, posted_at FROM posted_news ORDER BY posted_at DESC LIMIT 4"
    cursor.execute(query)
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
    db_posts = get_recent_posts_from_db()
    channel_posts = channel_checker.get_recent_posts(limit=10, since_time=since_time)
    recent_posts = db_posts + channel_posts
    if not recent_posts:
        return False
    existing_texts = [post['text'] for post in recent_posts]
    if has_gemini_key():
        ai_result = ai_checker.ai_compare_texts(new_text, existing_texts)
        if ai_result.get("ai_available"):
            return ai_result.get("is_duplicate", False)
    for existing_text in existing_texts:
        similarity = ai_checker.fallback_similarity_check(new_text, existing_text)
        if similarity >= threshold:
            return True
    return False


def check_articles_similarity(articles: List[Dict[str, Any]], threshold: float = 0.7) -> List[Dict[str, Any]]:
    """
    Проверяет статьи на дубликаты между собой (внутренняя проверка).
    Возвращает список уникальных статей.
    """
    if not articles:
        return []
    print(f"🔍 Проверяем {len(articles)} статей на внутренние дубликаты...")
    ai_checker = AIContentSimilarityChecker(threshold)
    unique_articles = []
    for i, article in enumerate(articles):
        article_text = article.get('post_text') or article.get('title', '')
        if not article_text:
            continue
        is_duplicate = False
        if unique_articles:
            existing_texts = [art.get('post_text', art.get('title', '')) for art in unique_articles]
            if has_gemini_key():
                ai_result = ai_checker.ai_compare_texts(article_text, existing_texts)
                if ai_result.get("ai_available"):
                    is_duplicate = ai_result.get("is_duplicate", False)
            else:
                max_similarity = 0.0
                for existing_text in existing_texts:
                    similarity = ai_checker.fallback_similarity_check(article_text, existing_text)
                    max_similarity = max(max_similarity, similarity)
                is_duplicate = max_similarity >= threshold
        if not is_duplicate:
            unique_articles.append(article)
    print(f"📊 Результат: {len(unique_articles)}/{len(articles)} уникальных статей")
    return unique_articles

