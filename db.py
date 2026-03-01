import psycopg2
from .config import DATABASE_URL

def get_db():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        telegram_id TEXT UNIQUE,
        name TEXT,
        message_count INT DEFAULT 0,
        last_reset DATE DEFAULT CURRENT_DATE,
        last_active TIMESTAMP DEFAULT NOW(),
        last_summary TEXT
    );
    """)

    conn.commit()
    cur.close()
    conn.close()
