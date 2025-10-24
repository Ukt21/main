
import sqlite3
from contextlib import contextmanager
from pathlib import Path

def init_db(db_path: str):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            '''CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                rating INTEGER NOT NULL,
                comment TEXT,
                promo_code TEXT,
                expires_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                resolved INTEGER DEFAULT 0
            )'''
        )
        conn.commit()

@contextmanager
def get_conn(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()
