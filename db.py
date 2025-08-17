import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

# Киевское время
KIEV_TZ = ZoneInfo("Europe/Kiev")

def now_kiev() -> datetime:
    """Возвращает текущее время в Киеве"""
    return datetime.now(KIEV_TZ)

def to_kiev_time(dt: datetime) -> datetime:
    """Преобразует datetime в киевское время"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KIEV_TZ)
    else:
        return dt.astimezone(KIEV_TZ)

def format_kiev_time(dt: datetime, format_str: str = '%H:%M %d.%m.%Y') -> str:
    """Форматирует время в киевском timezone"""
    if dt is None:
        return "неизвестно"
    kiev_dt = to_kiev_time(dt)
    return kiev_dt.strftime(format_str)

# Подключение к БД
db_path = os.path.join(os.path.dirname(__file__), "news.db")
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц
cursor.execute("""
CREATE TABLE IF NOT EXISTS posted_news (
    title TEXT PRIMARY KEY,
    post_text TEXT,
    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bot_runs (
    id INTEGER PRIMARY KEY,
    last_run TIMESTAMP
)
""")

# Обновление схемы (если старые таблицы)
try:
    cursor.execute("ALTER TABLE posted_news ADD COLUMN post_text TEXT")
    conn.commit()
except sqlite3.OperationalError:
    pass

try:
    cursor.execute("ALTER TABLE posted_news ADD COLUMN posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    conn.commit()
except sqlite3.OperationalError:
    pass


# === Работа с ботом и временем запусков ===
def get_last_run_time() -> Optional[datetime]:
    """Получает время последнего запуска бота"""
    cursor.execute("SELECT last_run FROM bot_runs ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if row and row[0]:
        return datetime.fromisoformat(row[0])
    return None

def update_last_run_time():
    """Обновляет время последнего запуска бота"""
    now = now_kiev().isoformat()
    cursor.execute("INSERT INTO bot_runs (last_run) VALUES (?)", (now,))
    conn.commit()


# === Работа с постами ===
def save_posted_news(title: str, post_text: Optional[str] = None):
    """Сохраняет новость в базу после публикации"""
    now = now_kiev().isoformat()
    cursor.execute(
        "INSERT OR REPLACE INTO posted_news (title, post_text, posted_at) VALUES (?, ?, ?)",
        (title, post_text, now)
    )
    conn.commit()

def is_news_posted(title: str) -> bool:
    """Проверяет, публиковалась ли уже новость с таким заголовком"""
    cursor.execute("SELECT 1 FROM posted_news WHERE title = ?", (title,))
    return cursor.fetchone() is not None

def get_recent_news(limit: int = 10) -> list:
    """Возвращает последние новости из базы"""
    cursor.execute("SELECT title, post_text, posted_at FROM posted_news ORDER BY posted_at DESC LIMIT ?", (limit,))
    return cursor.fetchall()
