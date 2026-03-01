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
# SILENCE DETECTION (48h)
# =============================

async def silence_check(context: ContextTypes.DEFAULT_TYPE):

    conn = get_db()
    cur = conn.cursor()

    threshold = datetime.utcnow() - timedelta(hours=48)

    cur.execute("""
        SELECT platform_user_id
        FROM users
        WHERE platform='telegram'
        AND last_active < %s
    """, (threshold,))

    users = cur.fetchall()

    for (user_id,) in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="Hey… thoda quiet ho gaye ho. Sab theek hai? 💛"
            )

            # Update to prevent repeated reminders
            cur.execute("""
                UPDATE users
                SET last_active = NOW()
                WHERE platform='telegram'
                AND platform_user_id=%s
            """, (user_id,))
            conn.commit()

        except:
            pass

    cur.close()
    conn.close()


# =============================
# WEEKLY MOOD SUMMARY
# =============================

async def weekly_mood_summary(context: ContextTypes.DEFAULT_TYPE):

    conn = get_db()
    cur = conn.cursor()

    one_week_ago = datetime.utcnow() - timedelta(days=7)

    # Find users with mood logs this week
    cur.execute("""
        SELECT DISTINCT platform_user_id
        FROM mood_logs
        WHERE platform='telegram'
        AND created_at >= %s
    """, (one_week_ago,))

    users = cur.fetchall()

    for (user_id,) in users:

        cur.execute("""
            SELECT mood_score, mood_label
            FROM mood_logs
            WHERE platform='telegram'
            AND platform_user_id=%s
            AND created_at >= %s
        """, (user_id, one_week_ago))

        moods = cur.fetchall()

        if not moods:
            continue

        scores = [m[0] for m in moods if m[0] is not None]
        labels = [m[1] for m in moods if m[1] is not None]

        if not scores:
            continue

        avg_mood = round(sum(scores) / len(scores), 1)
        most_common = max(set(labels), key=labels.count) if labels else "mixed"

        message = (
            "📊 Weekly Reflection 💛\n\n"
            f"This week you logged {len(scores)} mood check-ins.\n"
            f"Average mood: {avg_mood}/10\n"
            f"Most common feeling: {most_common}\n\n"
        )

        if avg_mood <= 4:
            message += "Lagta hai week thoda heavy tha… baat karna chahoge?"
        elif avg_mood <= 6:
            message += "Mixed week lag raha hai. Kuch ups and downs the."
        else:
            message += "Overall positive week tha ✨ Keep going."

        try:
            await context.bot.send_message(chat_id=user_id, text=message)
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

    # Silence check every 6 hours
    app.job_queue.run_repeating(silence_check, interval=21600, first=60)

    # Weekly mood summary (7 days)
    app.job_queue.run_repeating(weekly_mood_summary, interval=604800, first=120)

    print("Telegram bot running...")
    app.run_polling(drop_pending_updates=True)
