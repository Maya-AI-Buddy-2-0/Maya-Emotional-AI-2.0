from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from telegram import Update
from telegram.constants import ChatAction

from config import BOT_TOKEN
from maya_engine import generate_reply, daily_checkin_message, late_night_checkin_message
from db import get_db

from datetime import datetime, timedelta, time
import asyncio
import logging


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


# =============================
# MESSAGE HANDLER
# =============================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = str(update.message.from_user.id)
    name = update.message.from_user.first_name
    text = (update.message.text or "").strip()

    conn = get_db()
    cur = conn.cursor()

    # -----------------------------
    # CHECK USER
    # -----------------------------

    cur.execute("""
        SELECT onboarding_completed
        FROM users
        WHERE platform='telegram'
        AND platform_user_id=%s
    """, (user_id,))

    row = cur.fetchone()

    # -----------------------------
    # NEW USER
    # maya_engine will insert them
    # -----------------------------

    if row:

        onboarding_completed = row[0]

        if not onboarding_completed:

            await update.message.reply_text(
                "Hey 🙂 I'm Maya.\n\n"
                "You can talk to me about anything — what's going on today?"
            )

            cur.execute("""
                UPDATE users
                SET onboarding_completed = TRUE
                WHERE platform='telegram'
                AND platform_user_id=%s
            """, (user_id,))

            conn.commit()

            cur.close()
            conn.close()

            return

    cur.close()
    conn.close()

    # -----------------------------
    # TYPING INDICATOR
    # -----------------------------

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )

    # -----------------------------
    # AI GENERATION (non blocking)
    # -----------------------------

    try:

        reply = await asyncio.to_thread(
            generate_reply,
            "telegram",
            user_id,
            name,
            text
        )

    except Exception as e:

        logging.error(e)

        reply = "Hmm… thoda issue aa gaya. Ek baar phir bolo?"

    # -----------------------------
    # TYPING SIMULATION
    # -----------------------------

    typing_delay = random.uniform(1.5, 3.5)

    for _ in range(int(typing_delay)):

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )

        await asyncio.sleep(1)

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

            cur.execute("""
                UPDATE users
                SET last_active = NOW()
                WHERE platform='telegram'
                AND platform_user_id=%s
            """, (user_id,))

            conn.commit()

        except Exception as e:
            logging.error(e)

    cur.close()
    conn.close()


# =============================
# WEEKLY MOOD SUMMARY
# =============================

async def weekly_mood_summary(context: ContextTypes.DEFAULT_TYPE):

    conn = get_db()
    cur = conn.cursor()

    one_week_ago = datetime.utcnow() - timedelta(days=7)

    cur.execute("""
        SELECT DISTINCT platform_user_id
        FROM mood_logs
        WHERE platform='telegram'
        AND created_at >= %s
    """, (one_week_ago,))

    users = cur.fetchall()

    for (user_id,) in users:

        try:

            cur.execute("""
                SELECT mood_score, mood_label
                FROM mood_logs
                WHERE platform='telegram'
                AND platform_user_id=%s
                AND created_at >= %s
            """, (user_id, one_week_ago))

            moods = cur.fetchall()

            if len(moods) < 5:
                continue

            scores = [m[0] for m in moods if m[0] is not None]
            labels = [m[1] for m in moods if m[1] is not None]

            if not scores:
                continue

            avg_mood = round(sum(scores) / len(scores), 1)
            most_common = max(set(labels), key=labels.count)

            message = (
                "📊 Weekly Reflection 💛\n\n"
                f"Check-ins: {len(scores)}\n"
                f"Average mood: {avg_mood}/10\n"
                f"Most common feeling: {most_common}"
            )

            await context.bot.send_message(
                chat_id=user_id,
                text=message
            )

        except Exception as e:
            logging.error(e)

    cur.close()
    conn.close()


# =============================
# DAILY CHECK-IN
# =============================

async def daily_checkin(context: ContextTypes.DEFAULT_TYPE):

    conn = get_db()
    cur = conn.cursor()

    threshold = datetime.utcnow() - timedelta(days=7)

    cur.execute("""
        SELECT platform_user_id
        FROM users
        WHERE platform='telegram'
        AND last_active > %s
    """, (threshold,))

    users = cur.fetchall()

    for (user_id,) in users:

        try:

            await context.bot.send_message(
                chat_id=user_id,
                text=daily_checkin_message()
            )
            await asyncio.sleep(0.5)

        
        except Exception as e:
            logging.error(e)

    cur.close()
    conn.close()

# =============================
# LATE NIGHT CHECK-IN
# =============================

async def late_night_checkin(context: ContextTypes.DEFAULT_TYPE):

    conn = get_db()
    cur = conn.cursor()

    threshold = datetime.utcnow() - timedelta(days=7)

    cur.execute("""
        SELECT platform_user_id
        FROM users
        WHERE platform='telegram'
        AND last_active > %s
    """, (threshold,))

    users = cur.fetchall()

    for (user_id,) in users:

        try:

            await context.bot.send_message(
                chat_id=user_id,
                text=late_night_checkin_message()
            )

            await asyncio.sleep(0.5)
            

        except Exception as e:
            logging.error(e)

    cur.close()
    conn.close()

# =============================
# START BOT
# =============================

def start():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # silence check every 6 hours
    app.job_queue.run_repeating(
        silence_check,
        interval=21600,
        first=60
    )

    # weekly report (Sunday 8 PM)
    app.job_queue.run_daily(
        weekly_mood_summary,
        time=time(hour=20, minute=0),
        days=(6,)
    )

    # daily emotional check-in
    app.job_queue.run_daily(
        daily_checkin,
        time=time(hour=19, minute=0)
    )

    # late night emotional check-in
    app.job_queue.run_daily(
        late_night_checkin,
        time=time(hour=23, minute=30)
    )

    print("Telegram bot running...")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    start()
