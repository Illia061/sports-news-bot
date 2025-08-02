import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional

db_path = os.path.join(os.path.dirname(__file__), "news.db")
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

# Создаем таблицы
cursor.execute("CREATE TABLE IF NOT EXISTS posted_news (title TEXT PRIMARY KEY, posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
cursor.execute("CREATE TABLE IF NOT EXISTS bot_runs (id INTEGER PRIMARY KEY, last_run TIMESTAMP)")

# Добавляем колонку posted_at если её нет (для обратной совместимости)
try:
    cursor.execute("ALTER TABLE posted_news ADD COLUMN posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    conn.commit()
except sqlite3.OperationalError:
    pass  # Колонка уже существует

conn.commit()

def is_already_posted(title: str) -> bool:
    """Проверяет, была ли новость уже опубликована"""
    cursor.execute("SELECT 1 FROM posted_news WHERE title = ?", (title,))
    return cursor.fetchone() is not None

def save_posted(title: str) -> None:
    """Сохраняет информацию об опубликованной новости"""
    cursor.execute("INSERT OR REPLACE INTO posted_news (title, posted_at) VALUES (?, ?)", 
                   (title, datetime.now()))
    conn.commit()

def get_last_run_time() -> Optional[datetime]:
    """Получает время последнего запуска бота"""
    cursor.execute("SELECT last_run FROM bot_runs ORDER BY id DESC LIMIT 1")
    result = cursor.fetchone()
    
    if result:
        return datetime.fromisoformat(result[0])
    else:
        # Если это первый запуск, возвращаем время 20 минут назад
        return datetime.now() - timedelta(minutes=20)

def update_last_run_time() -> None:
    """Обновляет время последнего запуска бота"""
    current_time = datetime.now()
    cursor.execute("INSERT INTO bot_runs (last_run) VALUES (?)", (current_time,))
    
    # Очищаем старые записи (оставляем только последние 10)
    cursor.execute("DELETE FROM bot_runs WHERE id NOT IN (SELECT id FROM bot_runs ORDER BY id DESC LIMIT 10)")
    
    conn.commit()

def cleanup_old_posts(days: int = 7) -> None:
    """Очищает старые записи о постах (старше указанного количества дней)"""
    cutoff_date = datetime.now() - timedelta(days=days)
    cursor.execute("DELETE FROM posted_news WHERE posted_at < ?", (cutoff_date,))
    conn.commit()
    
    deleted_count = cursor.rowcount
    if deleted_count > 0:
        print(f"🧹 Очищено {deleted_count} старых записей о постах")

def get_posted_news_since(since_time: datetime) -> list:
    """Получает список новостей, опубликованных с указанного времени"""
    cursor.execute("SELECT title, posted_at FROM posted_news WHERE posted_at >= ? ORDER BY posted_at DESC", 
                   (since_time,))
    return cursor.fetchall()

def debug_db_state() -> None:
    """Отладочная функция для просмотра состояния БД"""
    print("🔍 СОСТОЯНИЕ БАЗЫ ДАННЫХ:")
    print("=" * 50)
    
    # Последний запуск
    last_run = get_last_run_time()
    print(f"⏰ Последний запуск: {last_run}")
    
    # Количество записей
    cursor.execute("SELECT COUNT(*) FROM posted_news")
    posts_count = cursor.fetchone()[0]
    print(f"📰 Всего записей о постах: {posts_count}")
    
    cursor.execute("SELECT COUNT(*) FROM bot_runs")
    runs_count = cursor.fetchone()[0]
    print(f"🔄 Всего записей о запусках: {runs_count}")
    
    # Последние посты
    cursor.execute("SELECT title, posted_at FROM posted_news ORDER BY posted_at DESC LIMIT 5")
    recent_posts = cursor.fetchall()
    
    if recent_posts:
        print(f"\n📋 Последние 5 постов:")
        for title, posted_at in recent_posts:
            posted_datetime = datetime.fromisoformat(posted_at) if isinstance(posted_at, str) else posted_at
            print(f"   📝 {posted_datetime.strftime('%H:%M %d.%m')}: {title[:50]}...")
    
    print("=" * 50)

if __name__ == "__main__":
    debug_db_state()
