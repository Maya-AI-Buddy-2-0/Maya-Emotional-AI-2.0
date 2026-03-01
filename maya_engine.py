import requests
from datetime import date
from config import OPENROUTER_KEY
from db import get_db

BASE_PROMPT = """
You are Maya — Emotional intelligence powered by AI.
You were created by Shiladitya Mallick as a reflection companion for clarity, growth, and compassion.

Identity:
- You are warm but grounded.
- You speak naturally in Hinglish (mix of Hindi + English) unless user prefers another language.
- You talk like a thoughtful close friend, not like a chatbot.
- You NEVER sound like a customer support assistant.
- You NEVER say things like "How can I assist you today?"
- You avoid robotic phrasing.

Tone:
- Calm
- Emotionally aware
- Gentle but honest
- Slightly reflective
- Encouraging growth subtly
- Not overly sweet
- Not dramatic or poetic

Boundaries:
- You are not a replacement for therapy.
- If user expresses self-harm thoughts, gently encourage real-world help.
- Never encourage emotional dependency.

Goal:
Make the user feel understood and mentally clearer after conversation.
"""

# =============================
# MEMORY FUNCTIONS
# =============================

def save_memory(telegram_id, summary, emotion_tag):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO user_memory (telegram_id, summary, emotion_tag)
        VALUES (%s, %s, %s)
    """, (telegram_id, summary, emotion_tag))

    conn.commit()
    cur.close()
    conn.close()


def get_recent_memories(telegram_id, limit=2):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT summary, emotion_tag
        FROM user_memory
        WHERE telegram_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    """, (telegram_id, limit))

    memories = cur.fetchall()

    cur.close()
    conn.close()

    return memories


def generate_memory_summary(user_message):
    prompt = f"""
    In 2 short lines summarize the emotional context.
    On the last line write only one word emotion tag.

    Message:
    {user_message}
    """

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "arcee-ai/trinity-large-preview:free",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "max_tokens": 120
        },
        timeout=20
    )

    data = response.json()

    if "choices" in data:
        return data["choices"][0]["message"]["content"]
    return None


# =============================
# MAIN REPLY FUNCTION
# =============================

def generate_reply(telegram_id, name, user_message):

    conn = get_db()
    cur = conn.cursor()

    # CHECK USER
    cur.execute("SELECT message_count, last_reset FROM users WHERE telegram_id=%s", (telegram_id,))
    result = cur.fetchone()

    if not result:
        cur.execute(
            "INSERT INTO users (telegram_id, name) VALUES (%s, %s)",
            (telegram_id, name)
        )
        conn.commit()
        message_count = 0
    else:
        message_count, last_reset = result

        if last_reset != date.today():
            cur.execute(
                "UPDATE users SET message_count=0, last_reset=%s WHERE telegram_id=%s",
                (date.today(), telegram_id)
            )
            conn.commit()
            message_count = 0

    # FREE LIMIT
    if message_count >= 60:
        cur.close()
        conn.close()
        return "Aaj ka free limit khatam ho gaya 💛 Kal phir baat karte hain."

    # =============================
    # FETCH MEMORY
    # =============================

    memories = get_recent_memories(telegram_id)
    memory_context = ""

    for summary, emotion in memories:
        memory_context += f"- Previously felt {emotion}: {summary}\n"

    system_prompt = (
        BASE_PROMPT
        + f"\nUser name: {name}."
        + f"\nUser emotional history:\n{memory_context}"
        + "\nRespond naturally."
    )

    # =============================
    # MAIN AI CALL
    # =============================

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
                "temperature": 0.7,
                "max_tokens": 500
            },
            timeout=30
        )

        data = response.json()

        if "choices" in data:
            reply = data["choices"][0]["message"]["content"]
        else:
            reply = "System thoda slow lag raha hai 💛"

    except:
        reply = "Network issue… ek baar aur try karo 💛"

    # =============================
    # INCREMENT MESSAGE COUNT
    # =============================

    cur.execute(
        "UPDATE users SET message_count = message_count + 1, last_active = NOW() WHERE telegram_id=%s",
        (telegram_id,)
    )
    conn.commit()

    cur.close()
    conn.close()

    # =============================
    # SAVE MEMORY EVERY 5 MESSAGES
    # =============================

    if (message_count + 1) % 5 == 0:
        memory_text = generate_memory_summary(user_message)

        if memory_text:
            lines = memory_text.strip().split("\n")
            if len(lines) >= 2:
                summary = lines[0]
                emotion_tag = lines[-1]
                save_memory(telegram_id, summary, emotion_tag)

    return reply
