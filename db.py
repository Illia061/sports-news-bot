
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "news.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS posted_news (title TEXT PRIMARY KEY)")
conn.commit()

def is_already_posted(title):
    cursor.execute("SELECT 1 FROM posted_news WHERE title = ?", (title,))
    return cursor.fetchone() is not None

def save_posted(title):
    cursor.execute("INSERT INTO posted_news (title) VALUES (?)", (title,))
    conn.commit()
