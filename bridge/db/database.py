import sqlite3
from pathlib import Path

DB_PATH = Path("data/actions.db")

def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    with open("bridge/db/schema.sql") as f:
        conn.executescript(f.read())
    # Ensure external_id column exists (safe to run multiple times)
    cur = conn.execute("PRAGMA table_info(actions)")
    cols = [r[1] for r in cur.fetchall()]
    if 'external_id' not in cols:
        conn.execute("ALTER TABLE actions ADD COLUMN external_id TEXT")
    conn.commit()
    conn.close()
