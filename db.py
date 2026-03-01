import psycopg2
from config import DATABASE_URL


def get_db():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # ============================
    # USERS TABLE (Multi-platform ready)
    # ============================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        platform TEXT NOT NULL,                 -- telegram / whatsapp / future
        platform_user_id TEXT NOT NULL,         -- telegram id or whatsapp number
        name TEXT,
        message_count INT DEFAULT 0,
        last_reset DATE DEFAULT CURRENT_DATE,
        last_active TIMESTAMP DEFAULT NOW(),
        last_summary TEXT,

        -- Premium ready (future use)
        is_premium BOOLEAN DEFAULT FALSE,
        premium_expires_at TIMESTAMP,

        UNIQUE(platform, platform_user_id)
    );
    """)

    # ============================
    # EMOTIONAL MEMORY TABLE
    # ============================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_memory (
        id SERIAL PRIMARY KEY,
        platform TEXT NOT NULL,
        platform_user_id TEXT NOT NULL,
        summary TEXT,
        emotion_tag TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """)

    # ============================
    # MOOD LOG TABLE (Future Step 3 ready)
    # ============================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS mood_logs (
        id SERIAL PRIMARY KEY,
        platform TEXT NOT NULL,
        platform_user_id TEXT NOT NULL,
        mood_score INT,
        mood_label TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """)

    conn.commit()
    cur.close()
    conn.close()
