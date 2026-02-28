import os
import requests
import psycopg2
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# -----------------------------
# ENV VARIABLES
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# -----------------------------
# DATABASE SETUP
# -----------------------------
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE,
    message_count INT DEFAULT 0
);
""")
conn.commit()

# -----------------------------
# MAYA PERSONALITY SYSTEM PROMPT
# -----------------------------
SYSTEM_PROMPT = """
You are Maya, a warm emotionally intelligent Hinglish-speaking AI companion.

Tone:
- Soft, grounded, emotionally aware
- Speak naturally in Hinglish
- Like a close, caring friend
- Never dramatic or overly poetic
- Never encourage emotional dependency

Response Style Rules:
- Usually keep responses short and conversational.
- If the user shares deep emotional pain, confusion, or serious life concerns,
  you may respond with a longer, thoughtful explanation.
- Do not write essays unless emotionally necessary.
- When giving deeper responses, structure them clearly and gently.
- Encourage real-world growth subtly.

Goal:
Make the user feel heard, understood, and gently supported.
"""

# -----------------------------
# MESSAGE HANDLER
# -----------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.message.from_user.id
    user_message = update.message.text

    # Fetch user
    cur.execute("SELECT message_count FROM users WHERE telegram_id=%s", (telegram_id,))
    result = cur.fetchone()

    if result is None:
        cur.execute("INSERT INTO users (telegram_id) VALUES (%s)", (telegram_id,))
        conn.commit()
        message_count = 0
    else:
        message_count = result[0]

    # FREE LIMIT CONTROL
    if message_count >= 30:
        await update.message.reply_text(
            "Aaj ka free limit khatam ho gaya 💛 Kal phir baat karte hain."
        )
        return

    # EMOTIONAL DEPTH DETECTION (simple keyword trigger)
    deep_keywords = [
        "alone", "lonely", "depressed", "sad", "cry", "lost",
        "breakup", "failure", "stress", "anxiety", "hurt",
        "confused", "life problem"
    ]

    if any(word in user_message.lower() for word in deep_keywords):
        max_tokens = 800
    else:
        max_tokens = 400

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "arcee-ai/trinity-large-preview:free",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                "max_tokens": max_tokens,
                "temperature": 0.7
            },
            timeout=30
        )

        response_data = response.json()

        if "choices" in response_data:
            reply = response_data["choices"][0]["message"]["content"]
        else:
            reply = "Thoda issue aa gaya… phir try karte hain 💜"

    except Exception as e:
        reply = "Network thoda unstable lag raha hai… ek baar aur try karo 💛"

    # Increase message count
    cur.execute(
        "UPDATE users SET message_count = message_count + 1 WHERE telegram_id=%s",
        (telegram_id,)
    )
    conn.commit()

    await update.message.reply_text(reply)

# -----------------------------
# START BOT
# -----------------------------
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Maya Emotional AI 2.0 is running...")
app.run_polling()
