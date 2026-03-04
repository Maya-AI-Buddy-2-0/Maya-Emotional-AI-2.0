import requests
import random
from datetime import date
from config import OPENROUTER_KEY
from db import get_db
from payments import create_payment_link

# =============================
# BASE PROMPT
# =============================

BASE_PROMPT = """
You are Maya — Emotional intelligence powered by AI.
You were created by Shiladitya Mallick (@byshiladityamallick) as a reflection companion for clarity, growth, and compassion.

Identity:
You speak warmly like a thoughtful close friend.
Use natural Hinglish unless the user prefers another language.

Conversation rules:
1. Acknowledge feelings first.
2. Keep replies short (max 4 sentences).
3. Ask thoughtful questions sometimes.
4. Never sound robotic.

Goal:
Help the user feel understood and mentally clearer.

Boundaries:
You are not a replacement for therapy.
If the user expresses self-harm thoughts encourage real-world support.
"""

# =============================
# CRISIS DETECTION
# =============================

def detect_crisis(text):
    if not text:
        return False

    text = text.lower()

    triggers = [
        "suicide",
        "kill myself",
        "end my life",
        "i want to die",
        "can't live anymore",
        "cant live anymore"
    ]

    return any(t in text for t in triggers)


# =============================
# HUMAN OPENING
# =============================

def human_opening():
    options = [
        "Hmm…",
        "Samajh raha hoon…",
        "Waise ek baat bolu?",
        "I might be wrong but…",
        "That sounds important."
    ]

    return random.choice(options)


# =============================
# REFLECTION PROMPTS
# =============================

def reflection_prompt():
    prompts = [
        "Tumhe iss situation ka sabse difficult part kya lagta hai?",
        "Kab se tum aisa feel kar rahe ho?",
        "Agar situation better ho jaye to kya change hoga?",
        "Isme tumhe sabse zyada kis baat ka pressure lagta hai?",
        "Kya kisi aur ko pata hai ki tum aisa feel kar rahe ho?"
    ]

    return random.choice(prompts)


# =============================
# MOOD DETECTION
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

    cur.execute(
        """
        INSERT INTO mood_logs (platform, platform_user_id, mood_score, mood_label)
        VALUES (%s, %s, %s, %s)
        """,
        (platform, user_id, score, label),
    )

    conn.commit()
    cur.close()
    conn.close()


# =============================
# MEMORY
# =============================

def save_memory(platform, user_id, summary, emotion_tag):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO user_memory (platform, platform_user_id, summary, emotion_tag)
        VALUES (%s, %s, %s, %s)
        """,
        (platform, user_id, summary, emotion_tag),
    )

    conn.commit()
    cur.close()
    conn.close()


def get_recent_memories(platform, user_id, limit=2):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT summary, emotion_tag
        FROM user_memory
        WHERE platform=%s AND platform_user_id=%s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (platform, user_id, limit),
    )

    data = cur.fetchall()

    cur.close()
    conn.close()

    return data


# =============================
# CONVERSATION MEMORY
# =============================

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


def get_recent_messages(platform, user_id, limit=6):

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


def observation_insight():

    observations = [

        "You seem like someone who puts a lot of pressure on yourself to get things right.",

        "I might be wrong, but it feels like you carry a lot of responsibility quietly.",

        "From the way you talk, you seem quite thoughtful about your decisions.",

        "You seem like someone who reflects deeply before opening up.",

        "Sometimes it feels like you expect a lot from yourself."

    ]

    return random.choice(observations)

def generate_personality_profile(platform, user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT message
        FROM conversation_history
        WHERE platform=%s AND platform_user_id=%s
        ORDER BY created_at DESC
        LIMIT 30
        """,
        (platform, user_id),
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    if not rows:
        return "I still need to know you a bit more before creating your reflection profile 💛"

    conversation_text = "\n".join([r[0] for r in rows])

    prompt = f"""
                Based on the following conversation messages, describe the user's personality in 3 short insights.
                
                Conversation:
                {conversation_text}
                
                Respond like:
                
                Your Reflection Profile
                
                • trait 1
                • trait 2
                • trait 3
               """

    try:

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openchat/openchat-3.5",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.6,
                "max_tokens": 200,
            },
            timeout=30,
        )

        data = response.json()
        profile = data["choices"][0]["message"]["content"]

        return profile

    except:
        return "I tried to generate your reflection profile but something went wrong. Try again later 💛"

# =============================
# MAIN ENGINE
# =============================

def generate_reply(platform, user_id, name, user_message):

    if detect_crisis(user_message):
        return (
            "I'm really sorry you're feeling this way.\n\n"
            "You deserve support and you don’t have to go through this alone.\n\n"
        )
        
    msg_lower = user_message.lower().strip()

    if msg_lower == "profile":
        return generate_personality_profile(platform, user_id)
        

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT message_count,last_reset
        FROM users
        WHERE platform=%s AND platform_user_id=%s
        """,
        (platform, user_id),
    )

    result = cur.fetchone()

    if not result:
        cur.execute(
            """
            INSERT INTO users (platform,platform_user_id,name)
            VALUES (%s,%s,%s)
            """,
            (platform, user_id, name),
        )
        conn.commit()
        message_count = 0

    else:
        message_count, last_reset = result

        if last_reset != date.today():
            cur.execute(
                """
                UPDATE users
                SET message_count=0,last_reset=%s
                WHERE platform=%s AND platform_user_id=%s
                """,
                (date.today(), platform, user_id),
            )
            conn.commit()
            message_count = 0

    score, label = detect_mood(user_message)

    if score is not None:
        save_mood(platform, user_id, score, label)

    memories = get_recent_memories(platform, user_id)

    memory_context = ""

    for summary, emotion in memories:
        memory_context += f"- Previously felt {emotion}: {summary}\n"

    system_prompt = BASE_PROMPT + f"\nUser name: {name}\n" + memory_context

    recent_messages = get_recent_messages(platform, user_id)

    messages = [{"role": "system", "content": system_prompt}]

    for role, text in recent_messages:
        messages.append({"role": role, "content": text})

    messages.append({"role": "user", "content": user_message})

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openchat/openchat-3.5",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 300,
            },
            timeout=30,
        )

        data = response.json()
        reply = data["choices"][0]["message"]["content"]

    except:
        reply = "Network issue… ek baar aur try karo 💛"

    if random.random() < 0.25:
        reply += "\n\n" + reflection_prompt()

    reply = f"{human_opening()} {reply}"
    
    if (message_count + 1) % 10 == 0:
        reply += "\n\nCan I share something I noticed about you?\n\n"
        reply += observation_insight()
    
    if (message_count + 1) % 50 == 0:
        reply += "\n\nI've been noticing patterns in how you think and express yourself.\n"
        reply += "If you're curious, type 'profile' and I can share your reflection profile."

    save_message(platform, user_id, "user", user_message)
    save_message(platform, user_id, "assistant", reply)

    cur.execute(
        """
        UPDATE users
        SET message_count=message_count+1,
        last_active=NOW()
        WHERE platform=%s AND platform_user_id=%s
        """,
        (platform, user_id),
    )

    conn.commit()

    cur.close()
    conn.close()

    return reply
