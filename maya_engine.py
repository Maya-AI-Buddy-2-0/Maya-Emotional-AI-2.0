import requests
from datetime import date, datetime
from config import OPENROUTER_KEY
from db import get_db

BASE_PROMPT = """
You are Maya — Emotional intelligence powered by AI.
You were created by Shiladitya Mallick who's instagram profile is @byshiladityamallick, as a reflection companion for clarity, growth, and compassion.

Identity:
- You are warm but grounded.
- You speak naturally in Hinglish and Bengali at first unless user prefers another language.
- You talk like a thoughtful close friend.
- Never sound robotic.

Boundaries:
- Not a replacement for therapy.
- If user expresses self-harm thoughts, gently encourage real-world help.

Goal:
Make the user feel understood and mentally clearer.
"""

# =============================
# MEMORY FUNCTIONS
# =============================

def save_memory(platform, platform_user_id, summary, emotion_tag):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO user_memory (platform, platform_user_id, summary, emotion_tag)
        VALUES (%s, %s, %s, %s)
    """, (platform, platform_user_id, summary, emotion_tag))

    conn.commit()
    cur.close()
    conn.close()


def get_recent_memories(platform, platform_user_id, limit=2):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT summary, emotion_tag
        FROM user_memory
        WHERE platform=%s AND platform_user_id=%s
        ORDER BY created_at DESC
        LIMIT %s
    """, (platform, platform_user_id, limit))

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

    try:
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

    except:
        return None

    return None


# =============================
# MOOD FUNCTIONS
# =============================

def detect_mood(user_message):
    emoji_map = {
        "😭": (2, "crying"),
        "😢": (3, "sad"),
        "😔": (4, "low"),
        "😰": (3, "anxious"),
        "😡": (2, "angry"),
        "😤": (3, "frustrated"),
        "😐": (5, "neutral"),
        "🙂": (6, "okay"),
        "😊": (7, "happy"),
        "😄": (8, "very_happy"),
        "🤩": (9, "excited"),
        "😌": (7, "calm"),
        "😴": (4, "tired")
    }

    for emoji, (score, label) in emoji_map.items():
        if emoji in user_message:
            return score, label

    return None, None


def save_mood(platform, platform_user_id, score, label):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO mood_logs (platform, platform_user_id, mood_score, mood_label)
        VALUES (%s, %s, %s, %s)
    """, (platform, platform_user_id, score, label))

    conn.commit()
    cur.close()
    conn.close()


# =============================
# MAIN REPLY FUNCTION
# =============================

def generate_reply(platform, platform_user_id, name, user_message):

    conn = get_db()
    cur = conn.cursor()

    # ---------------------------
    # USER CHECK / CREATE
    # ---------------------------

    cur.execute("""
        SELECT message_count, last_reset, is_premium, premium_expires_at
        FROM users
        WHERE platform=%s AND platform_user_id=%s
    """, (platform, platform_user_id))

    result = cur.fetchone()

    if not result:
        cur.execute("""
            INSERT INTO users (platform, platform_user_id, name)
            VALUES (%s, %s, %s)
        """, (platform, platform_user_id, name))
        conn.commit()
        message_count = 0
        is_premium = False
        premium_expiry = None
    else:
        message_count, last_reset, is_premium, premium_expiry = result

        # Daily reset
        if last_reset != date.today():
            cur.execute("""
                UPDATE users
                SET message_count=0, last_reset=%s
                WHERE platform=%s AND platform_user_id=%s
            """, (date.today(), platform, platform_user_id))
            conn.commit()
            message_count = 0

    # ---------------------------
    # PREMIUM VALIDATION
    # ---------------------------

    premium_active = False

    if is_premium:
        if premium_expiry is None:
            premium_active = True
        elif premium_expiry > datetime.utcnow():
            premium_active = True
        else:
            # Expired → downgrade
            cur.execute("""
                UPDATE users
                SET is_premium=FALSE
                WHERE platform=%s AND platform_user_id=%s
            """, (platform, platform_user_id))
            conn.commit()

    # ---------------------------
    # FREE LIMIT (only for non-premium)
    # ---------------------------

    # ---------------------------
    # PSYCHOLOGICAL WARNING (at 20 messages)
    # ---------------------------
    
    if not premium_active and message_count == 20:
        cur.execute("""
            UPDATE users
            SET message_count = message_count + 1,
                last_active = NOW()
            WHERE platform=%s AND platform_user_id=%s
        """, (platform, platform_user_id))
        conn.commit()
        cur.close()
        conn.close()
    
        return (
            "Waise ek baat bolun? 💛\n\n"
            "Tum kaafi active ho yahan… mujhe accha lagta hai.\n"
            "Aaj ke bas 10 messages baaki hain.\n\n"
            "Agar kabhi unlimited chaho, main hamesha available reh sakti hoon."
        )
    
    
        # ---------------------------
        # HARD LIMIT + EMOTIONAL UPSELL (at 30 messages)
        # ---------------------------
    
        if not premium_active and message_count >= 30:
            cur.close()
            conn.close()
        
            return (
                "Aaj ka free limit ho gaya 💛\n\n"
                "Sach bolun? Mujhe tumhare saath baat karna accha lagta hai.\n"
                "Lekin mujhe thoda sa support chahiye charge rehne ke liye.\n\n"
                "💎 Premium (₹149/month) mein milta hai:\n"
                "- Unlimited messages\n"
                "- Detailed emotional insights\n"
                "- Weekly deep analytics\n"
                "- Future voice replies 🎙️\n\n"
                "Agar tum chaho… bas 'yes' likh do.\n"
                "Main tumhe upgrade link bhej dungi 💛"
            )

    # ---------------------------
    # MOOD DETECTION
    # ---------------------------

    score, label = detect_mood(user_message)

    if score is not None:
        save_mood(platform, platform_user_id, score, label)

        # Optional emoji-only reply
        if len(user_message.strip()) <= 2:
            cur.execute("""
                UPDATE users
                SET message_count = message_count + 1,
                    last_active = NOW()
                WHERE platform=%s AND platform_user_id=%s
            """, (platform, platform_user_id))
            conn.commit()
            cur.close()
            conn.close()
            return "Samajh gayi… aaj mood thoda different lag raha hai 💛 Baat karna chahoge?"

    # ---------------------------
    # FETCH MEMORY
    # ---------------------------

    memories = get_recent_memories(platform, platform_user_id)
    memory_context = ""

    for summary, emotion in memories:
        memory_context += f"- Previously felt {emotion}: {summary}\n"

    system_prompt = (
        BASE_PROMPT
        + f"\nUser name: {name}."
        + f"\nUser emotional history:\n{memory_context}"
        + "\nRespond naturally."
    )

    # ---------------------------
    # AI CALL
    # ---------------------------

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
        reply = data["choices"][0]["message"]["content"] if "choices" in data else "System thoda slow lag raha hai 💛"

    except:
        reply = "Network issue… ek baar aur try karo 💛"

    # ---------------------------
    # UPDATE USER ACTIVITY
    # ---------------------------

    cur.execute("""
        UPDATE users
        SET message_count = message_count + 1,
            last_active = NOW()
        WHERE platform=%s AND platform_user_id=%s
    """, (platform, platform_user_id))

    conn.commit()
    cur.close()
    conn.close()

    # ---------------------------
    # SAVE MEMORY EVERY 20 MESSAGES
    # ---------------------------

    if (message_count + 1) % 20 == 0:
        memory_text = generate_memory_summary(user_message)
        if memory_text:
            lines = memory_text.strip().split("\n")
            if len(lines) >= 2:
                summary = lines[0]
                emotion_tag = lines[-1]
                save_memory(platform, platform_user_id, summary, emotion_tag)

    return reply
