from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from telegram import Update
from config import BOT_TOKEN
from maya_engine import generate_reply
from db import get_db
from datetime import datetime, timedelta


# =============================
# MESSAGE HANDLER
# =============================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    name = update.message.from_user.first_name
    text = update.message.text

    reply = generate_reply("telegram", user_id, name, text)

    await update.message.reply_text(reply)


# =============================
# SILENCE DETECTION JOB
# =============================

async def silence_check(context: ContextTypes.DEFAULT_TYPE):

    conn = get_db()
    cur = conn.cursor()

    threshold = datetime.utcnow() - timedelta(hours=48)

    cur.execute("""
        SELECT platform_user_id
        FROM users
        WHERE platform = 'telegram'
        AND last_active < %s
    """, (threshold,))

    users = cur.fetchall()

    for (user_id,) in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="Hey… thoda quiet ho gaye ho. Sab theek hai? 💛"
            )

            # Prevent spam — update last_active
            cur.execute("""
                UPDATE users
                SET last_active = NOW()
                WHERE platform='telegram' AND platform_user_id=%s
            """, (user_id,))
            conn.commit()

        except:
            pass

    cur.close()
    conn.close()


# =============================
# START BOT
# =============================

def start():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run silence check every 6 hours
    app.job_queue.run_repeating(silence_check, interval=21600, first=60)

    print("Telegram bot running...")
    app.run_polling(drop_pending_updates=True)
