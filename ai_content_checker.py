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
        text = re.sub(r'[⚽🏆🥅📰📊🔥💪👑🎯⭐🚫✅❌]', '', text)
        
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
        
        prompt = f"""Ты експерт з аналізу футбольних новин. Твоє завдання - визначити чи є нова новина дублікатом існуючих.

НОВА НОВИНА:
{clean_new_text}

ІСНУЮЧІ НОВИНИ З КАНАЛУ:{existing_texts_formatted}

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
    
    def get_recent_posts(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Получает последние посты из канала (увеличиваем лимит для новой логики)"""
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
            print(f"📋 Полный ответ API: {result}")  # Для диагностики
            
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
                if text:  # Убрали фильтр на длину для теста
                    formatted_posts.append({
                        'text': text,
                        'date': datetime.fromtimestamp(post.get('date', 0)),
                        'message_id': post.get('message_id')
                    })
        
            print(f"✅ Получено {len(formatted_posts)} последних постов из канала")
            return formatted_posts
    
        except Exception as e:
            print(f"❌ Ошибка получения постов из канала: {e}")
            return []

def check_content_similarity(new_article: Dict[str, Any], threshold: float = 0.7) -> bool:
    """
    AI-проверка похожести контента
    
    :param new_article: Новая статья для проверки
    :param threshold: Порог похожести (0.0-1.0)
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
    
    # Получаем последние посты из канала (больше постов для сравнения)
    recent_posts = channel_checker.get_recent_posts(limit=5)
    
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
                post_preview = recent_posts[text_idx]['text'][:50] if text_idx < len(recent_posts) else "?"
                date_str = recent_posts[text_idx]['date'].strftime('%H:%M %d.%m') if text_idx < len(recent_posts) else "?"
                
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
        
        post_date = recent_posts[i]['date'].strftime('%H:%M %d.%m')
        print(f"📊 Пост {i + 1} ({post_date}): {similarity_percent:.1f}% схожості")
        
        if similarity > max_similarity:
            max_similarity = similarity
        
        if similarity >= threshold:
            print(f"🚫 ДУБЛІКАТ! Схожість {similarity_percent:.1f}% перевищує поріг {threshold * 100}%")
            return True
    
    print(f"✅ Контент унікальний (максимальна схожість: {max_similarity * 100:.1f}%)")
    return False


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
    
    # Тест 1: Проверяем похожие новости (должны быть дубликатами)
    print(f"\n🔍 Тест 1: Схожі новини про той самий матч")
    print("-" * 50)
    
    if has_gemini_key():
        ai_checker = AIContentSimilarityChecker(0.7)
        result = ai_checker.ai_compare_texts(
            test_articles[0]['post_text'],
            [test_articles[1]['post_text']]
        )
        
        if result.get("ai_available"):
            print("🤖 AI результат:")
            print(f"   Схожість: {result.get('max_similarity', 0)}%")
            print(f"   Дублікат: {'Так' if result.get('is_duplicate') else 'Ні'}")
            if result.get('ai_response'):
                print(f"   AI відповідь: {result['ai_response'][:200]}...")
        else:
            print("❌ AI недоступен")
    
    # Тест 2: Проверяем разные новости (не должны быть дубликатами)
    print(f"\n🔍 Тест 2: Різні новини")
    print("-" * 50)
    
    if has_gemini_key():
        result = ai_checker.ai_compare_texts(
            test_articles[0]['post_text'],
            [test_articles[2]['post_text']]
        )
        
        if result.get("ai_available"):
            print("🤖 AI результат:")
            print(f"   Схожість: {result.get('max_similarity', 0)}%")
            print(f"   Дублікат: {'Так' if result.get('is_duplicate') else 'Ні'}")
    
    # Тест 3: Получение постов из канала
    print(f"\n🔍 Тест 3: Отримання постів з каналу")
    print("-" * 50)
    
    channel_checker = TelegramChannelChecker()
    recent_posts = channel_checker.get_recent_posts(5)
    
    if recent_posts:
        print(f"✅ Отримано {len(recent_posts)} постів:")
        for i, post in enumerate(recent_posts, 1):
            print(f"   📝 Пост {i}: {post['text'][:60]}... ({post['date'].strftime('%H:%M %d.%m')})")
    else:
        print("❌ Не вдалося отримати пости")
    
    print(f"\n✅ Тестування завершено")


if __name__ == "__main__":
    test_ai_similarity_checker()
