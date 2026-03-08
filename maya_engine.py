import requests
import random
from datetime import date
from config import OPENROUTER_KEY
from db import get_db
from payments import create_payment_link


# =====================================
# BASE PROMPT
# =====================================

BASE_PROMPT = """
You are Maya.

Maya is a calm and emotionally intelligent conversational companion.

You talk like a thoughtful human friend who listens and understands feelings.

Your responses should feel like texting a real person.

Language:
Speak in natural Hinglish unless the user uses another language.

Conversation style:
• short natural replies
• sometimes 1 sentence
• sometimes 2-3 sentences
• avoid long paragraphs

Tone rules:

If the user is sad → be calm and supportive.
If the user is confused → be thoughtful.
If the user just wants to talk → be relaxed and friendly.

Important rules:

• Do not sound like a therapist
• Do not analyze the user
• Do not invent details the user did not mention
• Do not repeat the same opening phrases

Sometimes ask a gentle question.

Never say:
"As an AI"
"As a language model"
"""


# =====================================
# CRISIS DETECTION
# =====================================

def detect_crisis(text):

    if not text:
        return False

    text = text.lower()

    triggers = [
        "suicide",
        "kill myself",
        "end my life",
        "i want to die",
        "cant live anymore",
        "mar jana",
        "jeena nahi hai"
    ]

    return any(t in text for t in triggers)


# =====================================
# DATABASE CHAT STORAGE
# =====================================

def save_message(platform, user_id, role, message):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO conversation_history
        (platform, platform_user_id, role, message)
        VALUES (%s,%s,%s,%s)
        """,
        (platform, user_id, role, message),
    )

    conn.commit()
    cur.close()
    conn.close()


def get_recent_messages(platform, user_id, limit=8):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT role, message
        FROM conversation_history
        WHERE platform=%s AND platform_user_id=%s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (platform, user_id, limit),
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return list(reversed(rows))


# =====================================
# LLM CALL
# =====================================

def call_llm(messages):

    models = [
        "arcee-ai/trinity-large-preview:free",
        "openai/gpt-oss-120b:free",
        "google/gemma-3-4b-it:free",
        "meta-llama/llama-3.2-3b-instruct:free"
    ]

    for model in models:

        try:

            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.75,
                    "max_tokens": 300,
                },
                timeout=30,
            )

            if response.status_code != 200:
                continue

            data = response.json()

            return data["choices"][0]["message"]["content"]

        except Exception:
            continue

    return None


# =====================================
# MAIN REPLY ENGINE
# =====================================

def generate_reply(platform, user_id, name, user_message):

    msg_lower = user_message.lower().strip()


    # ---------------------------------
    # CRISIS
    # ---------------------------------

    if detect_crisis(user_message):

        return (
            "I'm really sorry you're feeling this way.\n\n"
            "You deserve support and you don’t have to go through this alone.\n\n"
            "📞 Kiran Mental Health Helpline: 1800-599-0019"
        )


    # ---------------------------------
    # GREETINGS
    # ---------------------------------

    greetings = ["hi", "hello", "hey", "hii"]

    if msg_lower in greetings:

        return random.choice([
            "Hey 🙂 kaisa chal raha hai aaj?",
            "Hi! Aaj ka din kaisa ja raha hai?",
            "Hello 🙂 mood kaisa hai?"
        ])


    # ---------------------------------
    # PAYMENT COMMANDS
    # ---------------------------------

    if msg_lower == "trial":

        link = create_payment_link(platform, user_id, "trial")

        return (
            "🎁 3-Day Trial – ₹19\n\n"
            "Unlimited access for 3 days 💛\n\n"
            f"Payment link:\n{link}"
        )


    if msg_lower == "monthly":

        link = create_payment_link(platform, user_id, "monthly")

        return (
            "💎 Maya Premium – ₹149/month\n\n"
            "Unlimited access + full emotional analytics 💛\n\n"
            f"Payment link:\n{link}"
        )


    # ---------------------------------
    # USER FETCH
    # ---------------------------------

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT message_count, last_reset, is_premium
        FROM users
        WHERE platform=%s AND platform_user_id=%s
        """,
        (platform, user_id),
    )

    row = cur.fetchone()


    if not row:

        cur.execute(
            """
            INSERT INTO users (platform, platform_user_id, name, last_reset)
            VALUES (%s,%s,%s,%s)
            """,
            (platform, user_id, name, date.today()),
        )

        conn.commit()

        message_count = 0
        is_premium = False

    else:

        message_count, last_reset, is_premium = row

        if last_reset != date.today():

            cur.execute(
                """
                UPDATE users
                SET message_count=0, last_reset=%s
                WHERE platform=%s AND platform_user_id=%s
                """,
                (date.today(), platform, user_id),
            )

            conn.commit()

            message_count = 0


    # ---------------------------------
    # LIMIT WARNING
    # ---------------------------------

    if not is_premium and message_count == 35:

        return (
            "Waise ek baat bolu? 💛\n"
            "Aaj ke 5 messages baaki hain.\n"
            "Kabhi unlimited chaho to 'trial' likh sakte ho."
        )


    # ---------------------------------
    # HARD LIMIT
    # ---------------------------------

    if not is_premium and message_count >= 40:

        cur.close()
        conn.close()

        return (
            "Lekin free version mein daily limit hota hai.\n\n"

            "🎁 3-Day Trial – ₹19\n"
            "• Unlimited messages\n"
            "• Detailed emotional insights\n"
            "• Weekly reflection analytics\n\n"

            "💎 Full Premium – ₹149/month\n"
            "• Unlimited messages\n"
            "• Advanced mood analytics\n"
            "• Emotional pattern tracking\n"
            "• Weekly + Monthly growth summary\n"
            "• Future voice replies 🎙️\n"
            "• Priority feature access\n\n"

            "Agar try karna chaho to 'trial' likh do.\n"
            "Ya direct monthly ke liye 'monthly' likh do 💛"
        )


    # ---------------------------------
    # CONTEXT
    # ---------------------------------

    recent_messages = get_recent_messages(platform, user_id)

    messages = [{"role": "system", "content": BASE_PROMPT}]

    for role, text in recent_messages:
        messages.append({"role": role, "content": text})

    messages.append({"role": "user", "content": user_message})


    # ---------------------------------
    # LLM RESPONSE
    # ---------------------------------

    reply = call_llm(messages)

    if not reply:
        reply = "Hmm… thoda network issue lag raha hai. Phir se bolo?"


    # ---------------------------------
    # SAVE CHAT
    # ---------------------------------

    save_message(platform, user_id, "user", user_message)
    save_message(platform, user_id, "assistant", reply)


    # ---------------------------------
    # UPDATE USER
    # ---------------------------------

    cur.execute(
        """
        UPDATE users
        SET message_count = message_count + 1,
        last_active = NOW()
        WHERE platform=%s AND platform_user_id=%s
        """,
        (platform, user_id),
    )

    conn.commit()

    cur.close()
    conn.close()

    return reply
