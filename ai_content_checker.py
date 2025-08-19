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
    def __init__(self, similarity_threshold: float = 0.75):
        self.similarity_threshold = similarity_threshold
        if not has_gemini_key():
            print("⚠️ AI недоступен - будет использована базовая проверка")

    def clean_text_for_ai(self, text: str) -> str:
        """Улучшенная очистка текста с сохранением ключевой информации."""
        if not text:
            return ""
        
        # Убираем HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        
        # Убираем некоторые эмодзи, но оставляем важные
        text = re.sub(r'[📰📊🔥💪🎯⭐]', '', text)  # Убираем декоративные
        # Оставляем важные: ⚽🏆🥅✅❌🌍🚫👑
        
        # НЕ убираем источники - они помогают различать статьи
        # text = re.sub(r'(ESPN Soccer|Football\.ua|OneFootball)', '', text)  # ЗАКОММЕНТИРОВАНО
        
        # Убираем хэштеги в конце, но оставляем в середине текста
        text = re.sub(r'\s*#\w+\s*$', '', text)
        
        # Нормализуем пробелы
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def ai_compare_texts(self, new_text: str, existing_texts: List[str]) -> Dict[str, Any]:
        """Улучшенная AI-проверка дубликатов с детальным анализом."""
        if not has_gemini_key() or not model:
            return {"ai_available": False, "similarities": [], "is_duplicate": False}

        clean_new_text = self.clean_text_for_ai(new_text)
        clean_existing_texts = [self.clean_text_for_ai(text) for text in existing_texts]

        if not clean_new_text or not any(clean_existing_texts):
            return {"ai_available": True, "similarities": [], "is_duplicate": False}

        # УЛУЧШЕННЫЙ ПРОМПТ с детальными критериями
        prompt = f"""Ти експерт з аналізу футбольних новин. Порівняй НОВУ новину з ІСНУЮЧИМИ та визнач, чи є вона дублікатом.

КРИТЕРІЇ ДУБЛІКАТІВ:
- Та сама подія (матч, трансфер, нагорода) 
- Той самий гравець/команда в тій самій ситуації
- Той самий часовий період події

НЕ ВВАЖАЙ ДУБЛІКАТАМИ:
- Різні команди/гравці (навіть в схожих ситуаціях)
- Різні матчі/турніри
- Різні трансфери/нагороди
- Загальні футбольні терміни без конкретики

НОВА НОВИНА:
{clean_new_text}

ІСНУЮЧІ НОВИНИ:
{' | '.join([f"[{i+1}] {text}" for i, text in enumerate(clean_existing_texts)])}

Дай відповідь у форматі:
ДУБЛІКАТ: ТАК/НІ
ПОЯСНЕННЯ: [коротке обґрунтування]
СХОЖІСТЬ З: [номер існуючої новини або "ЖОДНА"]"""

        try:
            response = model.generate_content(prompt)
            ai_response = response.text.strip()
            
            # Парсим відповідь AI
            is_duplicate = False
            explanation = ""
            similar_to = "ЖОДНА"
            
            lines = ai_response.split('\n')
            for line in lines:
                if line.startswith('ДУБЛІКАТ:'):
                    is_duplicate = 'ТАК' in line.upper()
                elif line.startswith('ПОЯСНЕННЯ:'):
                    explanation = line.replace('ПОЯСНЕННЯ:', '').strip()
                elif line.startswith('СХОЖІСТЬ З:'):
                    similar_to = line.replace('СХОЖІСТЬ З:', '').strip()
            
            return {
                "ai_available": True,
                "ai_response": ai_response,
                "explanation": explanation,
                "similar_to": similar_to,
                "similarities": [],
                "is_duplicate": is_duplicate,
            }
        except Exception as e:
            print(f"❌ Ошибка AI анализа: {e}")
            return {"ai_available": False, "error": str(e), "similarities": [], "is_duplicate": False}

    def fallback_similarity_check(self, text1: str, text2: str) -> float:
        """Улучшенная fallback-проверка с учетом футбольной специфики."""
        if not text1 or not text2:
            return 0.0
        
        clean_text1 = self.clean_text_for_ai(text1).lower()
        clean_text2 = self.clean_text_for_ai(text2).lower()
        
        # Извлекаем ключевые сущности
        def extract_key_entities(text):
            # Команды (расширенный список)
            teams = re.findall(r'\b(?:реал|барселона|ліверпуль|манчестер|арсенал|челсі|рейнджерс|наполі|генк|астон вілла|клуб брюгге|баварія|ювентус|псж|атлетіко|севілья|валенсія|інтер|мілан|рома|лаціо|аталанта|фіорентина|реал мадрид|барселона|манчестер юнайтед|манчестер сіті|тоттенгем|ньюкасл|вест гем|лестер|евертон|саутгемптон|бернлі|фулгем|вольвз|брайтон|кристал палас|айпсвіч|борнмут)\b', text)
            
            # Игроки (имена с фамилиями на украинском/английском)
            players_ua = re.findall(r'\b[А-ЯІЇЄ][а-яіїєґ]+\s+[А-ЯІЇЄ][а-яіїєґ]+\b', text)
            players_en = re.findall(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', text)
            players = players_ua + players_en
            
            # Турниры/соревнования
            competitions = re.findall(r'\b(?:ліга чемпіонів|прем\'єр-ліга|ла ліга|серія а|бундесліга|pfa|uefa|ucl|champions league|premier league|la liga|serie a|bundesliga|europa league|conference league|fa cup|carabao cup|copa del rey|coppa italia|dfb pokal|кубок англії|кубок німеччини|кубок італії|кубок іспанії)\b', text)
            
            # Числа и суммы
            numbers = re.findall(r'\b\d+[\d\s]*(?:мільйонів?|голів?|асистів?|років?|хвилин?|million|goal|assist|year|minute)\b', text)
            
            return {
                'teams': set([team.lower() for team in teams]),
                'players': set([player.lower() for player in players]), 
                'competitions': set([comp.lower() for comp in competitions]),
                'numbers': set([num.lower() for num in numbers])
            }
        
        entities1 = extract_key_entities(clean_text1)
        entities2 = extract_key_entities(clean_text2)
        
        # Если есть пересечения по ключевым сущностям - высокий риск дубликата
        teams_overlap = len(entities1['teams'].intersection(entities2['teams']))
        players_overlap = len(entities1['players'].intersection(entities2['players']))
        competitions_overlap = len(entities1['competitions'].intersection(entities2['competitions']))
        
        # Если совпадают команды И игроки И соревнования - вероятный дубликат
        if teams_overlap > 0 and players_overlap > 0 and competitions_overlap > 0:
            return 0.9
        
        # Если совпадают 2 из 3 ключевых категорий - средний риск
        if (teams_overlap > 0 and players_overlap > 0) or \
           (teams_overlap > 0 and competitions_overlap > 0) or \
           (players_overlap > 0 and competitions_overlap > 0):
            return 0.7
        
        # Стандартная проверка по словам (с пониженным весом)
        words1 = set(clean_text1.split())
        words2 = set(clean_text2.split())
        
        # Расширенный список стоп-слов для футбола
        stop_words = {
            'в','на','за','до','від','для','про','під','над','при','з','у','і','та','або','але',
            'футбол','футбольний','гра','матч','команда','гравець','тренер','клуб','сезон',
            'гол','м\'яч','поле','стадіон','вболівальники','перемога','поразка', 'новини', 'спорт',
            'football', 'soccer', 'game', 'match', 'team', 'player', 'coach', 'club', 'season',
            'goal', 'ball', 'field', 'stadium', 'fans', 'win', 'loss', 'news', 'sport',
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'
        }
        
        words1 = {w for w in words1 if len(w) > 2 and w not in stop_words}
        words2 = {w for w in words2 if len(w) > 2 and w not in stop_words}
        
        if not words1 or not words2:
            return 0.0
        
        common_words = words1.intersection(words2)
        base_similarity = len(common_words) / max(len(words1), len(words2))
        
        # Возвращаем минимальную схожесть из entity-анализа и word-анализа
        return min(0.6, base_similarity)  # Максимум 0.6 для обычной схожести слов


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


def check_content_similarity(new_article: Dict[str, Any], threshold: float = 0.75, since_time: Optional[datetime] = None) -> bool:
    """Улучшенная проверка схожести с подробным логированием."""
    title = new_article.get('title', '')
    print(f"🔍 ДЕТАЛЬНАЯ AI проверка: {title[:60]}...")
    
    ai_checker = AIContentSimilarityChecker(threshold)
    channel_checker = TelegramChannelChecker()
    
    new_text = new_article.get('post_text') or new_article.get('title', '')
    if not new_text:
        return False
    
    db_posts = get_recent_posts_from_db()
    channel_posts = channel_checker.get_recent_posts(limit=10, since_time=since_time)
    recent_posts = db_posts + channel_posts
    
    if not recent_posts:
        print("   ✅ Нет предыдущих постов для сравнения")
        return False
    
    existing_texts = [post['text'] for post in recent_posts]
    print(f"   📊 Сравниваем с {len(existing_texts)} предыдущими постами")
    
    # Показываем что сравниваем
    print(f"   📝 НОВЫЙ ТЕКСТ: {new_text[:100]}...")
    for i, text in enumerate(existing_texts[:3], 1):  # Показываем первые 3
        print(f"   📝 СУЩЕСТВУЮЩИЙ {i}: {text[:100]}...")
    
    if has_gemini_key():
        print("   🤖 Используем AI-анализ...")
        ai_result = ai_checker.ai_compare_texts(new_text, existing_texts)
        
        if ai_result.get("ai_available"):
            is_duplicate = ai_result.get("is_duplicate", False)
            explanation = ai_result.get("explanation", "")
            similar_to = ai_result.get("similar_to", "ЖОДНА")
            
            print(f"   🤖 AI результат: {'ДУБЛИКАТ' if is_duplicate else 'УНИКАЛЬНАЯ'}")
            print(f"   📄 Пояснение: {explanation}")
            print(f"   🔗 Похожа на: {similar_to}")
            
            return is_duplicate
    
    print("   🔄 AI недоступен, используем fallback...")
    max_similarity = 0.0
    most_similar_text = ""
    
    for i, existing_text in enumerate(existing_texts, 1):
        similarity = ai_checker.fallback_similarity_check(new_text, existing_text)
        if similarity > max_similarity:
            max_similarity = similarity
            most_similar_text = existing_text
        print(f"   📊 Схожесть с #{i}: {similarity:.3f}")
    
    is_duplicate = max_similarity >= threshold
    
    print(f"   📊 МАКСИМАЛЬНАЯ схожесть: {max_similarity:.3f} (порог: {threshold})")
    print(f"   🔍 Наиболее похожий: {most_similar_text[:60]}...")
    print(f"   🎯 РЕЗУЛЬТАТ: {'ДУБЛИКАТ' if is_duplicate else 'УНИКАЛЬНАЯ'}")
    
    return is_duplicate


def check_articles_similarity(articles: List[Dict[str, Any]], threshold: float = 0.75) -> List[Dict[str, Any]]:
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
        duplicate_explanation = ""
        
        if unique_articles:
            existing_texts = [art.get('post_text', art.get('title', '')) for art in unique_articles]
            
            if has_gemini_key():
                print(f"   🔍 Проверяем статью {i+1}: {article.get('title', '')[:50]}...")
                ai_result = ai_checker.ai_compare_texts(article_text, existing_texts)
                
                if ai_result.get("ai_available"):
                    is_duplicate = ai_result.get("is_duplicate", False)
                    duplicate_explanation = ai_result.get("explanation", "")
                    similar_to = ai_result.get("similar_to", "ЖОДНА")
                    
                    if is_duplicate:
                        print(f"      🚫 ДУБЛИКАТ: {duplicate_explanation} (похожа на #{similar_to})")
                    else:
                        print(f"      ✅ УНИКАЛЬНАЯ: {duplicate_explanation}")
            else:
                max_similarity = 0.0
                for existing_text in existing_texts:
                    similarity = ai_checker.fallback_similarity_check(article_text, existing_text)
                    max_similarity = max(max_similarity, similarity)
                
                is_duplicate = max_similarity >= threshold
                
                if is_duplicate:
                    print(f"   🚫 Дубликат (схожесть: {max_similarity:.3f}): {article.get('title', '')[:50]}...")
                else:
                    print(f"   ✅ Уникальная (схожесть: {max_similarity:.3f}): {article.get('title', '')[:50]}...")
        
        if not is_duplicate:
            unique_articles.append(article)
    
    print(f"📊 Результат: {len(unique_articles)}/{len(articles)} уникальных статей")
    return unique_articles

