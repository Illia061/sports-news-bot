import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

KIEV_TZ = ZoneInfo("Europe/Kiev")

def now_kiev() -> datetime:
    return datetime.now(KIEV_TZ)

def to_kiev_time(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KIEV_TZ)
    else:
        return dt.astimezone(KIEV_TZ)

def format_kiev_time(dt: datetime, format_str: str = '%H:%M %d.%m.%Y') -> str:
    if dt is None:
        return "неизвестно"
    kiev_dt = to_kiev_time(dt)
    return kiev_dt.strftime(format_str)

db_path = os.path.join(os.path.dirname(__file__), "news.db")
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS posted_news (title TEXT PRIMARY KEY, post_text TEXT, posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
cursor.execute("CREATE TABLE IF NOT EXISTS bot_runs (id INTEGER PRIMARY KEY, last_run TIMESTAMP)")

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
