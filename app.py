import os
import requests
import psycopg2
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler
)

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
    message_count INT DEFAULT 0,
    voice_enabled BOOLEAN DEFAULT FALSE,
    last_active TIMESTAMP DEFAULT NOW()
);
""")
conn.commit()

# -----------------------------
# MAYA PERSONALITY
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
- Encourage real-world growth subtly.

Goal:
Make the user feel heard, understood, and gently supported.
"""

# -----------------------------
# SETTINGS BUTTON
# -----------------------------
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.message.from_user.id

    cur.execute("SELECT voice_enabled FROM users WHERE telegram_id=%s", (telegram_id,))
    result = cur.fetchone()
    voice_enabled = result[0] if result else False

    if voice_enabled:
        button = InlineKeyboardButton("🔇 Turn Voice Off", callback_data="voice_off")
        status = "Voice mode is ON 💜"
    else:
        button = InlineKeyboardButton("🔊 Turn Voice On", callback_data="voice_on")
        status = "Voice mode is OFF 🙂"

    keyboard = [[button]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(status, reply_markup=reply_markup)

# -----------------------------
# BUTTON HANDLER
# -----------------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    telegram_id = query.from_user.id
    await query.answer()

    if query.data == "voice_on":
        cur.execute("UPDATE users SET voice_enabled=TRUE WHERE telegram_id=%s", (telegram_id,))
        conn.commit()
        await query.edit_message_text("🔊 Voice mode enabled 💜")

    elif query.data == "voice_off":
        cur.execute("UPDATE users SET voice_enabled=FALSE WHERE telegram_id=%s", (telegram_id,))
        conn.commit()
        await query.edit_message_text("🔇 Voice mode disabled 🙂")

# -----------------------------
# MESSAGE HANDLER
# -----------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.message.from_user.id
    user_message = update.message.text

    # Check user
    cur.execute("SELECT message_count FROM users WHERE telegram_id=%s", (telegram_id,))
    result = cur.fetchone()

    if result is None:
        cur.execute("INSERT INTO users (telegram_id) VALUES (%s)", (telegram_id,))
        conn.commit()
        message_count = 0
    else:
        message_count = result[0]

    # Update last active
    cur.execute(
        "UPDATE users SET last_active = NOW() WHERE telegram_id=%s",
        (telegram_id,)
    )
    conn.commit()

    # Free limit
    if message_count >= 30:
        await update.message.reply_text(
            "Aaj ka free limit khatam ho gaya 💛 Kal phir baat karte hain."
        )
        return

    # Emotional depth detection
    deep_keywords = [
        "alone", "lonely", "depressed", "sad", "cry", "lost",
        "breakup", "failure", "stress", "anxiety", "hurt",
        "confused", "life problem"
    ]

    max_tokens = 800 if any(word in user_message.lower() for word in deep_keywords) else 400

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
        reply = response_data["choices"][0]["message"]["content"]

    except:
        reply = "Network thoda unstable lag raha hai… ek baar aur try karo 💛"

    # Increase message count
    cur.execute(
        "UPDATE users SET message_count = message_count + 1 WHERE telegram_id=%s",
        (telegram_id,)
    )
    conn.commit()

    await update.message.reply_text(reply)

# -----------------------------
# SILENCE TRIGGER (24h)
# -----------------------------
async def silence_check(app):
    cur.execute("""
        SELECT telegram_id 
        FROM users 
        WHERE last_active < NOW() - INTERVAL '24 hours'
    """)
    users = cur.fetchall()

    for user in users:
        try:
            await app.bot.send_message(
                chat_id=user[0],
                text="Hey… aaj thoda quiet ho tum 💛 Sab theek hai?"
            )

            # Prevent repeat spam
            cur.execute(
                "UPDATE users SET last_active = NOW() WHERE telegram_id=%s",
                (user[0],)
            )
            conn.commit()

        except:
            pass

# -----------------------------
# START BOT
# -----------------------------
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("settings", settings_menu))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(
    lambda: app.create_task(silence_check(app)),
    "interval",
    hours=3
)
scheduler.start()

print("Maya Emotional AI 2.0 is running...")
app.run_polling()
