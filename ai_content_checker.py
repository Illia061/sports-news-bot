
import re
import os
import requests
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import google.generativeai as genai
from cachetools import TTLCache
import difflib

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_AVAILABLE = False
model = None

def init_gemini():
    """Инициализирует клиента Gemini."""
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

def clean_text_for_ai(text: str) -> str:
    """Очищает текст для AI-анализа."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s*#\w+\s*', ' ', text)
    text = re.sub(r'[⚽🏆🥅📰📊🔥💪👑🎯⭐🚫✅❌🌍]', '', text)
    text = re.sub(r'(ESPN Soccer|Football\.ua|OneFootball)', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.replace('**', '')
    return text

class AIContentSimilarityChecker:
    """AI-проверка похожести контента через Gemini."""
    
    def __init__(self, similarity_threshold: float = 0.7):
        self.similarity_threshold = similarity_threshold
        if not has_gemini_key():
            print("⚠️ AI недоступен - будет использована базовая проверка")
    
    def ai_compare_texts(self, new_text: str, existing_texts: List[str], batch_size: int = 5) -> Dict[str, Any]:
        """Использует AI для сравнения текстов в пакетном режиме."""
        if not has_gemini_key() or not model:
            return {"ai_available": False, "similarities": [], "is_duplicate": False}
        
        clean_new_text = clean_text_for_ai(new_text)
        clean_existing_texts = [clean_text_for_ai(text) for text in existing_texts]
        
        if not clean_new_text or not any(clean_existing_texts):
            return {"ai_available": True, "similarities": [], "is_duplicate": False}
        
        similarities = []
        is_duplicate = False
        max_similarity = 0
        
        for i in range(0, len(clean_existing_texts), batch_size):
            batch_texts = clean_existing_texts[i:i + batch_size]
            if not batch_texts:
                continue
            
            existing_texts_formatted = "\n".join(f"Текст {j+1}: {text}" for j, text in enumerate(batch_texts) if text)
            if not existing_texts_formatted:
                continue
            
            prompt = f"""Ти експерт з аналізу футбольних новин. Твоє завдання - визначити чи є нова новина дублікатом існуючих.

НОВА НОВИНА:
{clean_new_text}

ІСНУЮЧІ НОВИНИ:{existing_texts_formatted}

ЗАВДАННЯ:
1. Порівняй нову новину з кожною існуючою
2. Визнач семантичну схожість (не тільки дослівну)
3. Враховуй що однакові події можуть бути описані по-різному
4. Враховуй контекст футболу - різні матчі, різні команди це РІЗНІ новини
5. Однак одна і та ж подія (той самий матч, той самий трансфер) це ДУБЛІКАТ

КРИТЕРІЇ ДУБЛІКАТУ:
- Та ж футбольна подія (матч, трансфер, травма гравця тощо)
- Ті ж основні факти, навіть якщо по-різному сформульовані
- Той самий результат матчу між тими ж командами

НЕ ДУБЛІКАТ:
- Різні матчі (навіть тих самих команд в різний час)
- Різні гравці або команди
- Різні події навіть в рамках одного матчу

ФОРМАТ ВІДПОВІДІ (дуже важливо дотримуватися):
АНАЛІЗ:
Текст 1: [схожість 0-100%] - [пояснення]
Текст 2: [схожість 0-100%] - [пояснення]
Текст 3: [схожість 0-100%] - [пояснення]

ВИСНОВОК: [ТАК/НІ] - [обґрунтування]

Будь точним та обґрунтованим у своєму аналізі."""
            
            try:
                print(f"🤖 Відправляю {len(clean_new_text)} символів на AI аналіз дубликатів...")
                response = model.generate_content(prompt)
                ai_response = response.text.strip()
                
                print(f"🤖 AI відповідь отримана: {len(ai_response)} символів")
                
                batch_matches = re.findall(r'Текст (\d+): (\d+)%', ai_response)
                for match in batch_matches:
                    text_num = int(match[0]) - 1 + i
                    similarity_percent = int(match[1])
                    similarities.append({
                        'text_index': text_num,
                        'similarity_percent': similarity_percent,
                        'similarity_ratio': similarity_percent / 100.0
                    })
                    max_similarity = max(max_similarity, similarity_percent)
                
                if 'ВИСНОВОК: ТАК' in ai_response.upper():
                    is_duplicate = True
                    break
            except Exception as e:
                print(f"❌ Помилка AI аналізу для пакета {i//batch_size + 1}: {e}")
                continue
        
        return {
            "ai_available": True,
            "ai_response": ai_response if 'ai_response' in locals() else "",
            "similarities": similarities,
            "is_duplicate": is_duplicate,
            "max_similarity": max_similarity
        }
    
    def fallback_similarity_check(self, text1: str, text2: str) -> float:
        """Резервная проверка похожести без AI."""
        if not text1 or not text2:
            return 0.0
        
        clean_text1 = clean_text_for_ai(text1).lower()
        clean_text2 = clean_text_for_ai(text2).lower()
        
        matcher = difflib.SequenceMatcher(None, clean_text1, clean_text2)
        similarity = matcher.ratio()
        
        key_terms = {'шахтар', 'динамо', 'реал', 'барселона', 'мбаппе', 'роналду'}
        words1 = set(clean_text1.split())
        words2 = set(clean_text2.split())
        common_key_terms = key_terms.intersection(words1).intersection(words2)
        
        if common_key_terms:
            similarity = min(1.0, similarity + 0.2)
        
        return similarity

class TelegramChannelChecker:
    """Класс для получения последних сообщений из Telegram канала."""
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
        self.cache = TTLCache(maxsize=10, ttl=300)  # Кэш на 5 минут
    
    def get_recent_posts(self, limit: int = 5, since_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Получает последние посты из канала с кэшированием."""
        cache_key = (limit, since_time.isoformat() if since_time else None)
        if cache_key in self.cache:
            print("✅ Используем кэшированные посты")
            return self.cache[cache_key]
        
        if not self.bot_token or not self.channel_id:
            print("❌ Telegram настройки не найдены")
            return []
    
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {'limit': 100, 'offset': -100}
            response = requests.get(url, params=params, timeout=30)
            result = response.json()
            
            if not result.get('ok'):
                print(f"❌ Ошибка получения обновлений: {result.get('description')}")
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
        
            print(f"✅ Получено {len(formatted_posts)} последних постов из канала")
            self.cache[cache_key] = formatted_posts
            return formatted_posts
    
        except Exception as e:
            print(f"❌ Ошибка получения постов из канала: {e}")
            return []

def check_content_similarity(new_article: Dict[str, Any], threshold: float = 0.7, since_time: Optional[datetime] = None) -> bool:
    """Проверяет похожесть контента с постами в канале."""
    print(f"🔍 AI проверка дубликатов: {new_article.get('title', '')[:50]}...")
    
    ai_checker = AIContentSimilarityChecker(threshold)
    channel_checker = TelegramChannelChecker()
    
    new_text = new_article.get('post_text') or new_article.get('title', '')
    if not new_text:
        print("⚠️ Новая статья не содержит текста")
        return False
    
    recent_posts = channel_checker.get_recent_posts(limit=10, since_time=since_time)
    
    if not recent_posts:
        print("✅ Не удалось получить недавние посты - публикуем")
        return False
    
    existing_texts = [post['text'] for post in recent_posts]
    
    print(f"📊 Сравниваем с {len(existing_texts)} недавними постами...")
    
    if has_gemini_key():
        print("🤖 Используем AI для анализа похожести...")
        ai_result = ai_checker.ai_compare_texts(new_text, existing_texts)
        
        if ai_result.get("ai_available"):
            print("✅ AI анализ выполнен:")
            
            for similarity in ai_result.get("similarities", []):
                text_idx = similarity['text_index']
                percent = similarity['similarity_percent']
                if text_idx < len(recent_posts):
                    post_preview = recent_posts[text_idx]['text'][:50]
                    date_str = recent_posts[text_idx]['date'].strftime('%H:%M %d.%m')
                    print(f"   📊 Пост {text_idx + 1} ({date_str}): {percent}% схожості")
                    print(f"      📄 {post_preview}...")
            
            is_duplicate = ai_result.get("is_duplicate", False)
            max_similarity = ai_result.get("max_similarity", 0)
            
            if is_duplicate:
                print(f"🚫 AI ВИСНОВОК: ДУБЛІКАТ! (максимальна схожість: {max_similarity}%)")
                print(f"📝 AI пояснення:")
                ai_response = ai_result.get("ai_response", "")
                if "ВИСНОВОК:" in ai_response:
                    conclusion_part = ai_response.split("ВИСНОВОК:")[1][:200]
                    print(f"   {conclusion_part}...")
            else:
                print(f"✅ AI ВИСНОВОК: УНІКАЛЬНИЙ КОНТЕНТ (максимальна схожість: {max_similarity}%)")
            
            return is_duplicate
        else:
            print("⚠️ AI недоступен, используем резервную проверку")
    
    print("🔧 Используем базовую проверку похожести...")
    max_similarity = 0.0
    
    for i, existing_text in enumerate(existing_texts):
        similarity = ai_checker.fallback_similarity_check(new_text, existing_text)
        similarity_percent = similarity * 100
        
        if i < len(recent_posts):
            post_date = recent_posts[i]['date'].strftime('%H:%M %d.%m')
            print(f"📊 Пост {i + 1} ({post_date}): {similarity_percent:.1f}% схожості")
        
        if similarity > max_similarity:
            max_similarity = similarity
        
        if similarity >= threshold:
            print(f"🚫 ДУБЛІКАТ! Схожість {similarity_percent:.1f}% перевищує поріг {threshold * 100}%")
            return True
    
    print(f"✅ Контент унікальний (максимальна схожість: {max_similarity * 100:.1f}%)")
    return False

def check_articles_similarity(articles: List[Dict[str, Any]], threshold: float = 0.7) -> List[Dict[str, Any]]:
    """Проверяет статьи на дубликаты между собой."""
    if not articles:
        return []
    
    print(f"🔍 Проверяем {len(articles)} статей на внутренние дубликаты...")
    
    ai_checker = AIContentSimilarityChecker(threshold)
    unique_articles = []
    
    for i, article in enumerate(articles):
        print(f"📰 Проверяем статью {i+1}/{len(articles)}: {article.get('title', '')[:50]}...")
        
        article_text = article.get('post_text') or article.get('title', '')
        
        if not article_text:
            print("⚠️ Статья не содержит текста - пропускаем")
            continue
        
        is_duplicate = False
        
        if unique_articles:
            existing_texts = [art.get('post_text', art.get('title', '')) for art in unique_articles]
            
            if has_gemini_key():
                ai_result = ai_checker.ai_compare_texts(article_text, existing_texts)
                
                if ai_result.get("ai_available"):
                    is_duplicate = ai_result.get("is_duplicate", False)
                    max_similarity = ai_result.get("max_similarity", 0)
                    
                    if is_duplicate:
                        print(f"🚫 AI: Дублікат! (схожість: {max_similarity}%)")
                        for similarity in ai_result.get("similarities", []):
                            if similarity['similarity_percent'] >= threshold * 100:
                                idx = similarity['text_index']
                                if idx < len(unique_articles):
                                    similar_title = unique_articles[idx].get('title', '')[:50]
                                    print(f"   📄 Схожа з: {similar_title}...")
                                break
                    else:
                        print(f"✅ AI: Унікальна (макс. схожість: {max_similarity}%)")
                else:
                    print("⚠️ AI недоступен для внутренней проверки")
            else:
                max_similarity = 0.0
                for existing_text in existing_texts:
                    similarity = ai_checker.fallback_similarity_check(article_text, existing_text)
                    max_similarity = max(max_similarity, similarity)
                
                is_duplicate = max_similarity >= threshold
                print(f"🔧 Базовая проверка: {'Дублікат' if is_duplicate else 'Унікальна'} (схожість: {max_similarity * 100:.1f}%)")
        
        if not is_duplicate:
            unique_articles.append(article)
            print(f"✅ Статья добавлена в список уникальных")
        
        if has_gemini_key():
            time.sleep(0.5)
    
    print(f"📊 Результат внутренней проверки: {len(unique_articles)}/{len(articles)} уникальных статей")
    return unique_articles

def test_ai_similarity_checker():
    """Тестирует AI проверку похожести."""
    print("🧪 ТЕСТИРОВАНИЕ AI ПРОВЕРКИ ПОХОЖЕСТИ")
    print("=" * 60)
    
    if not has_gemini_key():
        print("❌ AI недоступен - тестируем базовую проверку")
    else:
        print("✅ AI доступен - тестируем полную систему")
    
    test_articles = [
        {
            'title': 'Шахтар переміг Динамо з рахунком 2:1',
            'post_text': '<b>⚽ Шахтар переміг Динамо з рахунком 2:1</b>\n\nВ чемпіонаті України відбувся принциповий матч між Шахтар та Динамо. Перемогу здобув Шахтар завдяки голам у другому тайме.\n\n#футбол #новини'
        },
        {
            'title': 'Динамо програло Шахтарю 1:2 в чемпіонаті',
            'post_text': '<b>⚽ Динамо програло Шахтарю</b>\n\nУ вчорашньому матчі УПЛ Динамо поступилося Шахтарю з рахунком 1:2. Матч пройшов в напруженій боротьбі.\n\n#футбол #УПЛ'
        },
        {
            'title': 'Мбаппе забив два голи за Реал Мадрид',
            'post_text': '<b>⚽ Мбаппе - герой матчу</b>\n\nФранцузький форвард відзначився дублем у матчі Ла Ліги проти Барселони. Реал переміг 3:1.\n\n#футбол #Реал'
        }
    ]
    
    print(f"\n🔍 Тест: Внутренняя проверка дубликатов")
    print("-" * 50)
    
    unique_articles = check_articles_similarity(test_articles, 0.7)
    
    print(f"✅ Тестирование завершено")
    print(f"📊 Результат: {len(unique_articles)}/{len(test_articles)} уникальных статей")

if __name__ == "__main__":
    test_ai_similarity_checker()
