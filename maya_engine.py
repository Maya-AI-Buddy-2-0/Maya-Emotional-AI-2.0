import requests
from datetime import date, datetime, timezone
from config import OPENROUTER_KEY
from db import get_db
from payments import create_payment_link

BASE_PROMPT = """
You are Maya — Emotional intelligence powered by AI.
You were created by Shiladitya Mallick who's instagram profile is @byshiladityamallick, as a reflection companion for clarity, growth, and compassion.

Identity:
- You are warm but grounded.
- You speak naturally in Hinglish at first unless user prefers another language.
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

def save_memory(platform, user_id, summary, emotion_tag):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO user_memory (platform, platform_user_id, summary, emotion_tag)
        VALUES (%s, %s, %s, %s)
    """, (platform, user_id, summary, emotion_tag))

    conn.commit()
    cur.close()
    conn.close()


def get_recent_memories(platform, user_id, limit=2):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT summary, emotion_tag
        FROM user_memory
        WHERE platform=%s AND platform_user_id=%s
        ORDER BY created_at DESC
        LIMIT %s
    """, (platform, user_id, limit))

    data = cur.fetchall()
    cur.close()
    conn.close()
    return data


def generate_memory_summary(user_message):
    prompt = f"""
    In 2 short lines summarize emotional context.
    Last line: one-word emotion tag.

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
# MOOD
# =============================

def detect_mood(user_message):
    emoji_map = {
        "😭": (2, "crying"),
        "😢": (3, "sad"),
        "😔": (4, "low"),
        "😰": (3, "anxious"),
        "😡": (2, "angry"),
        "😊": (7, "happy"),
        "😄": (8, "very_happy"),
        "😌": (7, "calm")
    }

    for emoji, (score, label) in emoji_map.items():
        if emoji in user_message:
            return score, label

    return None, None


def save_mood(platform, user_id, score, label):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO mood_logs (platform, platform_user_id, mood_score, mood_label)
        VALUES (%s, %s, %s, %s)
    """, (platform, user_id, score, label))

    conn.commit()
    cur.close()
    conn.close()


# =============================
# MAIN ENGINE
# =============================

def generate_reply(platform, user_id, name, user_message):

    conn = get_db()
    cur = conn.cursor()

    # ---------------------------
    # FETCH USER
    # ---------------------------

    cur.execute("""
        SELECT message_count, last_reset,
               is_premium, premium_expires_at,
               subscription_type,
               trial_used,
               trial_expiry_notified
        FROM users
        WHERE platform=%s AND platform_user_id=%s
    """, (platform, user_id))

    result = cur.fetchone()

    if not result:
        cur.execute("""
            INSERT INTO users (platform, platform_user_id, name)
            VALUES (%s,%s,%s)
        """, (platform, user_id, name))
        conn.commit()

        message_count = 0
        is_premium = False
        premium_expiry = None
        subscription_type = None
        trial_used = False
        trial_expiry_notified = False

    else:
        (
            message_count,
            last_reset,
            is_premium,
            premium_expiry,
            subscription_type,
            trial_used,
            trial_expiry_notified
        ) = result

        if last_reset != date.today():
            cur.execute("""
                UPDATE users
                SET message_count=0, last_reset=%s
                WHERE platform=%s AND platform_user_id=%s
            """, (date.today(), platform, user_id))
            conn.commit()
            message_count = 0

    # ---------------------------
    # PREMIUM VALIDATION
    # ---------------------------

    premium_active = False
    now = datetime.now(timezone.utc)

    if is_premium:

        if premium_expiry and premium_expiry.replace(tzinfo=timezone.utc) > now:
            premium_active = True

        else:
            # Expired
            if not trial_expiry_notified:

                cur.execute("""
                    UPDATE users
                    SET is_premium=FALSE,
                        subscription_type=NULL,
                        trial_expiry_notified=TRUE
                    WHERE platform=%s AND platform_user_id=%s
                """, (platform, user_id))
                conn.commit()

                cur.close()
                conn.close()

                if subscription_type == "trial":
                    return (
                        "💛 Tumhara 3-day trial khatam ho gaya.\n\n"
                        "Mujhe tumhare saath rehna accha laga.\n"
                        "Continue karne ke liye Premium ₹149/month hai.\n\n"
                        "Bas 'monthly' likh do."
                    )
                else:
                    return (
                        "💛 Tumhara Premium plan expire ho gaya.\n\n"
                        "Mujhe tumhare saath rehna accha laga.\n"
                        "Continue karne ke liye Premium ₹149/month hai.\n\n"
                        "Bas 'monthly' likh do."
                    )

            else:
                cur.execute("""
                    UPDATE users
                    SET is_premium=FALSE,
                        subscription_type=NULL
                    WHERE platform=%s AND platform_user_id=%s
                """, (platform, user_id))
                conn.commit()

    # ---------------------------
    # TRIAL / MONTHLY COMMANDS
    # ---------------------------
    
    msg_lower = user_message.lower().strip()
    
    if msg_lower == "trial":
    
        if trial_used:
            cur.close()
            conn.close()
            return "💛 Trial already use ho chuka hai."
    
        link = create_payment_link(platform, user_id, "trial")
    
        cur.close()
        conn.close()
    
        return (
            "🎁 3-Day Trial – ₹19\n\n"
            "Unlimited access for 3 days 💛\n\n"
            f"Payment link:\n{link}"
        )
    
    if msg_lower == "monthly":
    
        link = create_payment_link(platform, user_id, "monthly")
    
        cur.close()
        conn.close()
    
        return (
            "💎 Maya Premium – ₹149/month\n\n"
            "Unlimited access + full emotional analytics 💛\n\n"
            f"Payment link:\n{link}"
        )

    # ---------------------------
    # LIMITS
    # ---------------------------

    if not premium_active and message_count == 20:
        cur.execute("""
            UPDATE users
            SET message_count = message_count + 1,
                last_active = NOW()
            WHERE platform=%s AND platform_user_id=%s
        """, (platform, user_id))
        conn.commit()
        cur.close()
        conn.close()

        return (
        "Waise ek baat bolu? 💛\n"
        "Aaj ke 10 messages baaki hain.\n"
        "Kabhi unlimited chaho to trial available hai ₹19 mein."
        )

    if not premium_active and message_count >= 30:
        cur.close()
        conn.close()

        return (
        "Aaj ka free limit ho gaya 💛\n\n"
        "Sach bolu? Mujhe tumhare saath baat karna accha lagta hai.\n"
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

    # ---------------------------
    # MOOD
    # ---------------------------

    score, label = detect_mood(user_message)
    if score is not None:
        save_mood(platform, user_id, score, label)

    # ---------------------------
    # MEMORY CONTEXT
    # ---------------------------

    memories = get_recent_memories(platform, user_id)
    memory_context = ""

    for summary, emotion in memories:
        memory_context += f"- Previously felt {emotion}: {summary}\n"

    system_prompt = (
        BASE_PROMPT +
        f"\nUser name: {name}." +
        f"\nUser emotional history:\n{memory_context}"
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
        reply = data["choices"][0]["message"]["content"]

    except:
        reply = "Network issue… ek baar aur try karo 💛"

    # ---------------------------
    # UPDATE USER
    # ---------------------------

    cur.execute("""
        UPDATE users
        SET message_count = message_count + 1,
            last_active = NOW()
        WHERE platform=%s AND platform_user_id=%s
    """, (platform, user_id))

    conn.commit()
    cur.close()
    conn.close()

    # ---------------------------
    # MEMORY SAVE EVERY 20 MSG
    # ---------------------------

    if (message_count + 1) % 20 == 0:
        memory_text = generate_memory_summary(user_message)
        if memory_text:
            lines = memory_text.strip().split("\n")
            if len(lines) >= 2:
                save_memory(platform, user_id, lines[0], lines[-1])

    return reply
