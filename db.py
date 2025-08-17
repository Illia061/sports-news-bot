import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

# Киевское время
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

# Таблицы
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

# Обновление схемы (если старые версии)
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

conn.commit()


# === API для работы с новостями и запуском ===
def is_already_posted(title: str) -> bool:
    cursor.execute("SELECT 1 FROM posted_news WHERE title = ?", (title,))
    return cursor.fetchone() is not None

def save_posted(title: str, post_text: Optional[str] = None) -> None:
    """Сохраняет публикацию (заголовок + текст)"""
    kiev_now = now_kiev()
    cursor.execute(
        "INSERT OR REPLACE INTO posted_news (title, post_text, posted_at) VALUES (?, ?, ?)",
        (title, post_text, kiev_now.isoformat())
    )
    conn.commit()
    print(f"💾 Сохранена запись о публикации в {format_kiev_time(kiev_now)}: {title[:50]}...")

def get_last_run_time() -> Optional[datetime]:
    cursor.execute("SELECT last_run FROM bot_runs ORDER BY id DESC LIMIT 1")
    result = cursor.fetchone()
    if result:
        try:
            last_run_str = result[0]
            if isinstance(last_run_str, str):
                last_run_dt = datetime.fromisoformat(last_run_str)
            else:
                last_run_dt = last_run_str
            return to_kiev_time(last_run_dt)
        except Exception as e:
            print(f"⚠️ Ошибка парсинга времени последнего запуска: {e}")
            return now_kiev() - timedelta(minutes=20)
    else:
        return now_kiev() - timedelta(minutes=20)

def update_last_run_time() -> None:
    current_time_kiev = now_kiev()
    cursor.execute("INSERT INTO bot_runs (last_run) VALUES (?)", (current_time_kiev.isoformat(),))
    cursor.execute("DELETE FROM bot_runs WHERE id NOT IN (SELECT id FROM bot_runs ORDER BY id DESC LIMIT 10)")
    conn.commit()
    print(f"⏰ Обновлено время последнего запуска: {format_kiev_time(current_time_kiev)}")

def cleanup_old_posts(days: int = 7) -> None:
    cutoff_date_kiev = now_kiev() - timedelta(days=days)
    cursor.execute("DELETE FROM posted_news WHERE posted_at < ?", (cutoff_date_kiev.isoformat(),))
    conn.commit()
    deleted_count = cursor.rowcount
    if deleted_count > 0:
        print(f"🧹 Очищено {deleted_count} старых записей о постах (старше {days} дней)")

def get_posted_news_since(since_time: datetime) -> list:
    since_time_kiev = to_kiev_time(since_time)
    cursor.execute("SELECT title, post_text, posted_at FROM posted_news WHERE posted_at >= ? ORDER BY posted_at DESC",
                   (since_time_kiev.isoformat(),))
    return cursor.fetchall()

def debug_db_state() -> None:
    print("🔍 СОСТОЯНИЕ БАЗЫ ДАННЫХ:")
    print("=" * 50)
    current_kiev = now_kiev()
    print(f"🕒 Текущее время (Киев): {format_kiev_time(current_kiev)}")
    last_run = get_last_run_time()
    print(f"⏰ Последний запуск: {format_kiev_time(last_run)}")
    if last_run:
        time_diff = current_kiev - to_kiev_time(last_run)
        print(f"⏱️  Разница: {time_diff.total_seconds() / 60:.1f} минут")
    cursor.execute("SELECT COUNT(*) FROM posted_news")
    posts_count = cursor.fetchone()[0]
    print(f"📰 Всего записей о постах: {posts_count}")
    cursor.execute("SELECT COUNT(*) FROM bot_runs")
    runs_count = cursor.fetchone()[0]
    print(f"🔄 Всего записей о запусках: {runs_count}")
    cursor.execute("SELECT title, post_text, posted_at FROM posted_news ORDER BY posted_at DESC LIMIT 5")
    recent_posts = cursor.fetchall()
    if recent_posts:
        print(f"\n📋 Последние 5 постов:")
        for title, post_text, posted_at in recent_posts:
            try:
                posted_datetime = datetime.fromisoformat(posted_at) if isinstance(posted_at, str) else posted_at
                posted_kiev = to_kiev_time(posted_datetime)
                preview = post_text if post_text else title
                print(f"   📝 {format_kiev_time(posted_kiev, '%H:%M %d.%m')}: {preview[:50]}...")
            except Exception as e:
                print(f"   📝 {posted_at}: {title[:50]}... (ошибка парсинга времени: {e})")
    cursor.execute("SELECT last_run FROM bot_runs ORDER BY id DESC LIMIT 3")
    recent_runs = cursor.fetchall()
    if recent_runs:
        print(f"\n🔄 Последние 3 запуска:")
        for i, (run_time,) in enumerate(recent_runs, 1):
            try:
                run_datetime = datetime.fromisoformat(run_time) if isinstance(run_time, str) else run_time
                run_kiev = to_kiev_time(run_datetime)
                print(f"   🔄 {i}. {format_kiev_time(run_kiev)}")
            except Exception as e:
                print(f"   🔄 {i}. {run_time} (ошибка парсинга: {e})")
    print("=" * 50)

if __name__ == "__main__":
    debug_db_state()

