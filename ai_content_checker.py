import re
import os
import requests
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import google.generativeai as genai

# Используем настройки AI из ai_processor
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_AVAILABLE = False
model = None

def init_gemini():
    """Инициализирует клиента Gemini"""
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
    """AI-проверка похожести контента через Gemini"""
    
    def __init__(self, similarity_threshold: float = 0.7):
        """
        :param similarity_threshold: Порог похожести (0.0-1.0)
        """
        self.similarity_threshold = similarity_threshold
        if not has_gemini_key():
            print("⚠️ AI недоступен - будет использована базовая проверка")
    
    def clean_text_for_ai(self, text: str) -> str:
        """Очищает текст для AI анализа"""
        if not text:
            return ""
        
        # Убираем HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        
        # Убираем хештеги (но оставляем основной текст)
        text = re.sub(r'\s*#\w+\s*', ' ', text)
        
        # Убираем лишние символы и эмодзи
        text = re.sub(r'[⚽🏆🥅📰📊🔥💪👑🎯⭐🚫✅❌🌍]', '', text)
        
        # Убираем источники
        text = re.sub(r'(ESPN Soccer|Football\.ua|OneFootball)', '', text)
        
        # Убираем лишние пробелы
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def ai_compare_texts(self, new_text: str, existing_texts: List[str]) -> Dict[str, Any]:
        """Использует AI для сравнения текстов"""
        if not has_gemini_key() or not model:
            return {"ai_available": False, "similarities": [], "is_duplicate": False}
        
        # Очищаем тексты
        clean_new_text = self.clean_text_for_ai(new_text)
        clean_existing_texts = [self.clean_text_for_ai(text) for text in existing_texts]
        
        if not clean_new_text or not any(clean_existing_texts):
            return {"ai_available": True, "similarities": [], "is_duplicate": False}
        
        # Формируем промпт для AI
        existing_texts_formatted = ""
        for i, text in enumerate(clean_existing_texts, 1):
            if text:  # Только непустые тексты
                existing_texts_formatted += f"\nТекст {i}: {text}\n"
        
        if not existing_texts_formatted:
            return {"ai_available": True, "similarities": [], "is_duplicate": False}
        
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
            print(f"🤖 Відправляю {len(clean_new_text)} символів на AI аналіз дублікатів...")
            response = model.generate_content(prompt)
            ai_response = response.text.strip()
            
            print(f"🤖 AI відповідь отримана: {len(ai_response)} символів")
            
            # Парсимо відповідь AI
            similarities = []
            is_duplicate = False
            
            # Шукаємо схожості в тексті
            similarity_pattern = r'Текст (\d+): (\d+)%'
            matches = re.findall(similarity_pattern, ai_response)
            
            for match in matches:
                text_num = int(match[0])
                similarity_percent = int(match[1])
                similarities.append({
                    'text_index': text_num - 1,
                    'similarity_percent': similarity_percent,
                    'similarity_ratio': similarity_percent / 100.0
                })
            
            # Шукаємо висновок
            if 'ВИСНОВОК: ТАК' in ai_response.upper():
                is_duplicate = True
            elif 'ВИСНОВОК: НІ' in ai_response.upper():
                is_duplicate = False
            else:
                # Резервна логіка - якщо схожість > 70%
                max_similarity = max([s['similarity_percent'] for s in similarities]) if similarities else 0
                is_duplicate = max_similarity >= (self.similarity_threshold * 100)
            
            return {
                "ai_available": True,
                "ai_response": ai_response,
                "similarities": similarities,
                "is_duplicate": is_duplicate,
                "max_similarity": max([s['similarity_percent'] for s in similarities]) if similarities else 0
            }
            
        except Exception as e:
            print(f"❌ Помилка AI аналізу: {e}")
            return {"ai_available": False, "error": str(e), "similarities": [], "is_duplicate": False}
    
    def fallback_similarity_check(self, text1: str, text2: str) -> float:
        """Резервная проверка похожести без AI"""
        if not text1 or not text2:
            return 0.0
        
        # Простое сравнение ключевых слов
        words1 = set(self.clean_text_for_ai(text1).lower().split())
        words2 = set(self.clean_text_for_ai(text2).lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        # Фильтруем стоп-слова
        stop_words = {'в', 'на', 'за', 'до', 'від', 'для', 'про', 'під', 'над', 'при', 'з', 'у', 'і', 'та', 'або', 'але'}
        words1 = {w for w in words1 if len(w) > 2 and w not in stop_words}
        words2 = {w for w in words2 if len(w) > 2 and w not in stop_words}
        
        if not words1 or not words2:
            return 0.0
        
        # Вычисляем пересечение
        common_words = words1.intersection(words2)
        similarity = len(common_words) / max(len(words1), len(words2))
        
        return similarity


class TelegramChannelChecker:
    """Класс для получения последних сообщений из Telegram канала"""
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
    
    def get_recent_posts(self, limit: int = 5, since_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Получает последние посты из канала"""
        if not self.bot_token or not self.channel_id:
            print("❌ Telegram настройки не найдены")
            return []
    
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {
                'limit': 100,
                'offset': -100
            }
            
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
            return formatted_posts
    
        except Exception as e:
            print(f"❌ Ошибка получения постов из канала: {e}")
            return []

def check_content_similarity(new_article: Dict[str, Any], threshold: float = 0.7, since_time: Optional[datetime] = None) -> bool:
    """
    AI-проверка похожести контента с проверкой каналов
    
    :param new_article: Новая статья для проверки
    :param threshold: Порог похожести (0.0-1.0)
    :param since_time: Время, начиная с которого проверять дубликаты (опционально)
    :return: True если контент похож (нужно пропустить), False если уникален (можно публиковать)
    """
    print(f"🔍 AI проверка дубликатов: {new_article.get('title', '')[:50]}...")
    
    # Создаем проверяльщики
    ai_checker = AIContentSimilarityChecker(threshold)
    channel_checker = TelegramChannelChecker()
    
    # Получаем текст новой статьи
    new_text = new_article.get('post_text') or new_article.get('title', '')
    if not new_text:
        print("⚠️ Новая статья не содержит текста")
        return False
    
    # Получаем последние посты из канала с фильтром по времени
    recent_posts = channel_checker.get_recent_posts(limit=10, since_time=since_time)
    
    if not recent_posts:
        print("✅ Не удалось получить недавние посты - публикуем")
        return False
    
    # Извлекаем тексты для сравнения
    existing_texts = [post['text'] for post in recent_posts]
    
    print(f"📊 Сравниваем с {len(existing_texts)} недавними постами...")
    
    # Используем AI для анализа
    if has_gemini_key():
        print("🤖 Используем AI для анализа похожести...")
        ai_result = ai_checker.ai_compare_texts(new_text, existing_texts)
        
        if ai_result.get("ai_available"):
            print("✅ AI анализ выполнен:")
            
            # Показываем результаты сравнения
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
                # Показываем часть AI ответа с выводом
                ai_response = ai_result.get("ai_response", "")
                if "ВИСНОВОК:" in ai_response:
                    conclusion_part = ai_response.split("ВИСНОВОК:")[1][:200]
                    print(f"   {conclusion_part}...")
            else:
                print(f"✅ AI ВИСНОВОК: УНІКАЛЬНИЙ КОНТЕНТ (максимальна схожість: {max_similarity}%)")
            
            return is_duplicate
        else:
            print("⚠️ AI недоступен, используем резервную проверку")
    
    # Резервная проверка без AI
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
    """
    Проверяет статьи на дубликаты между собой (внутренняя проверка)
    Возвращает список уникальных статей
    """
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
        
        # Сравниваем с уже добавленными уникальными статьями
        if unique_articles:
            existing_texts = [art.get('post_text', art.get('title', '')) for art in unique_articles]
            
            if has_gemini_key():
                # Используем AI для сравнения
                ai_result = ai_checker.ai_compare_texts(article_text, existing_texts)
                
                if ai_result.get("ai_available"):
                    is_duplicate = ai_result.get("is_duplicate", False)
                    max_similarity = ai_result.get("max_similarity", 0)
                    
                    if is_duplicate:
                        print(f"🚫 AI: Дублікат! (схожість: {max_similarity}%)")
                        # Найдем с какой именно статьей дубликат
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
                # Используем базовую проверку
                max_similarity = 0.0
                for existing_text in existing_texts:
                    similarity = ai_checker.fallback_similarity_check(article_text, existing_text)
                    max_similarity = max(max_similarity, similarity)
                
                is_duplicate = max_similarity >= threshold
                print(f"🔧 Базовая проверка: {'Дублікат' if is_duplicate else 'Унікальна'} (схожість: {max_similarity * 100:.1f}%)")
        
        # Если не дубликат, добавляем в список уникальных
        if not is_duplicate:
            unique_articles.append(article)
            print(f"✅ Статья добавлена в список уникальных")
        
        # Небольшая пауза для AI
        if has_gemini_key():
            time.sleep(0.5)
    
    print(f"📊 Результат внутренней проверки: {len(unique_articles)}/{len(articles)} уникальных статей")
    return unique_articles


def test_ai_similarity_checker():
    """Тестирует AI проверку похожести"""
    print("🧪 ТЕСТИРОВАНИЕ AI ПРОВЕРКИ ПОХОЖЕСТИ")
    print("=" * 60)
    
    if not has_gemini_key():
        print("❌ AI недоступен - тестируем базовую проверку")
    else:
        print("✅ AI доступен - тестируем полную систему")
    
    # Тестовые данные
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
    
    # Тест: Внутренняя проверка дубликатов
    print(f"\n🔍 Тест: Внутренняя проверка дубликатов")
    print("-" * 50)
    
    unique_articles = check_articles_similarity(test_articles, 0.7)
    
    print(f"✅ Тестирование завершено")
    print(f"📊 Результат: {len(unique_articles)}/{len(test_articles)} уникальных статей")


if __name__ == "__main__":
    test_ai_similarity_checker()
