import os
import requests
import psycopg2
from datetime import datetime, date
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
# DB CONNECTION HELPER
# -----------------------------
def get_db():
    return psycopg2.connect(DATABASE_URL)

# -----------------------------
# INITIAL TABLE SETUP
# -----------------------------
conn = get_db()
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE,
    name TEXT,
    message_count INT DEFAULT 0,
    last_reset DATE DEFAULT CURRENT_DATE,
    voice_enabled BOOLEAN DEFAULT FALSE,
    last_active TIMESTAMP DEFAULT NOW(),
    last_reminder TIMESTAMP,
    last_summary TEXT
);
""")

conn.commit()
cur.close()
conn.close()

# -----------------------------
# SYSTEM PROMPT TEMPLATE
# -----------------------------
BASE_PROMPT = """
You are Maya, a warm emotionally intelligent Hinglish-speaking AI companion.

Tone:
- Soft, grounded, emotionally aware
- Speak naturally in Hinglish
- Like a close, caring friend
- Never dramatic or overly poetic
- Never encourage emotional dependency

Safety:
If user expresses self-harm or suicidal thoughts:
- Encourage real-world support
- Suggest talking to trusted people
- Never position yourself as sole support

Goal:
Make the user feel heard, understood, and gently supported.
"""

# -----------------------------
# SETTINGS MENU
# -----------------------------
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.message.from_user.id
    conn = get_db()
    cur = conn.cursor()

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

    cur.close()
    conn.close()

# -----------------------------
# BUTTON HANDLER
# -----------------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    telegram_id = query.from_user.id
    await query.answer()

    conn = get_db()
    cur = conn.cursor()

    if query.data == "voice_on":
        cur.execute("UPDATE users SET voice_enabled=TRUE WHERE telegram_id=%s", (telegram_id,))
        await query.edit_message_text("🔊 Voice mode enabled 💜")

    elif query.data == "voice_off":
        cur.execute("UPDATE users SET voice_enabled=FALSE WHERE telegram_id=%s", (telegram_id,))
        await query.edit_message_text("🔇 Voice mode disabled 🙂")

    conn.commit()
    cur.close()
    conn.close()

# -----------------------------
# MESSAGE HANDLER
# -----------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    user_message = update.message.text

    conn = get_db()
    cur = conn.cursor()

    # Fetch user
    cur.execute("""
        SELECT message_count, last_reset, last_summary
        FROM users WHERE telegram_id=%s
    """, (telegram_id,))
    result = cur.fetchone()

    if result is None:
        cur.execute("""
            INSERT INTO users (telegram_id, name)
            VALUES (%s, %s)
        """, (telegram_id, user_name))
        conn.commit()
        message_count = 0
        last_reset = date.today()
        last_summary = None
    else:
        message_count, last_reset, last_summary = result

    # Daily reset
    if last_reset != date.today():
        cur.execute("""
            UPDATE users
            SET message_count=0, last_reset=%s
            WHERE telegram_id=%s
        """, (date.today(), telegram_id))
        conn.commit()
        message_count = 0

    # Free limit check
    if message_count >= 30:
        await update.message.reply_text(
            "Aaj ka free limit khatam ho gaya 💛 Kal phir baat karte hain."
        )
        cur.close()
        conn.close()
        return

    # Update last active
    cur.execute(
        "UPDATE users SET last_active=NOW() WHERE telegram_id=%s",
        (telegram_id,)
    )
    conn.commit()

    # Emotional depth detection
    deep_keywords = [
        "alone","lonely","depressed","sad","cry","lost",
        "breakup","failure","stress","anxiety","hurt",
        "confused","life","empty","meaningless"
    ]

    max_tokens = 800 if any(word in user_message.lower() for word in deep_keywords) else 400

    # Dynamic system prompt
    system_prompt = BASE_PROMPT + f"\nUser name is {user_name}."

    if last_summary:
        system_prompt += f"\nPrevious emotional context: {last_summary}"

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
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "max_tokens": max_tokens,
                "temperature": 0.7
            },
            timeout=30
        )

        data = response.json()

        if "choices" in data:
            reply = data["choices"][0]["message"]["content"]
        else:
            reply = "Aaj thoda system slow lag raha hai 💛"

    except Exception:
        reply = "Network thoda unstable lag raha hai… ek baar aur try karo 💛"

    # Increment message count
    cur.execute("""
        UPDATE users
        SET message_count = message_count + 1
        WHERE telegram_id=%s
    """, (telegram_id,))
    conn.commit()

    # Store emotional summary every 5 messages
    if message_count % 5 == 0:
        try:
            summary_response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "arcee-ai/trinity-large-preview:free",
                    "messages": [
                        {"role": "system", "content": "Summarize user's emotional state in one short sentence."},
                        {"role": "user", "content": user_message}
                    ],
                    "max_tokens": 50,
                    "temperature": 0.3
                }
            )

            summary_data = summary_response.json()
            if "choices" in summary_data:
                summary = summary_data["choices"][0]["message"]["content"]
                cur.execute("""
                    UPDATE users
                    SET last_summary=%s
                    WHERE telegram_id=%s
                """, (summary, telegram_id))
                conn.commit()
        except:
            pass

    await update.message.reply_text(reply)

    cur.close()
    conn.close()

# -----------------------------
# SILENCE REMINDER SYSTEM
# -----------------------------
async def silence_check(app):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT telegram_id
        FROM users
        WHERE last_active < NOW() - INTERVAL '24 hours'
        AND (last_reminder IS NULL OR last_reminder < NOW() - INTERVAL '24 hours')
    """)

    users = cur.fetchall()

    for user in users:
        try:
            await app.bot.send_message(
                chat_id=user[0],
                text="Hey… aaj thoda quiet ho tum 💛 Sab theek hai?"
            )

            cur.execute("""
                UPDATE users
                SET last_reminder=NOW()
                WHERE telegram_id=%s
            """, (user[0],))
            conn.commit()

        except:
            pass

    cur.close()
    conn.close()

# -----------------------------
# START BOT
# -----------------------------
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("settings", settings_menu))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

scheduler = BackgroundScheduler()
scheduler.add_job(
    lambda: app.create_task(silence_check(app)),
    "interval",
    hours=3
)
scheduler.start()

print("Maya Emotional AI 2.1 is running...")
app.run_polling()
