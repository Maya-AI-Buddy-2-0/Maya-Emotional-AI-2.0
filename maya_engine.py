import requests
import random
import time
from datetime import date, datetime
from config import OPENROUTER_KEY
from db import get_db
from payments import create_payment_link

# =============================
# BASE PROMPT
# =============================

BASE_PROMPT = """
You are Maya — Emotional intelligence powered by AI.
You were created by Shiladitya Mallick (@byshiladityamallick) as a reflection companion for clarity, growth, and compassion.
Talk like a caring human friend, not like an AI analyzing the user.

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
        "cant live anymore",
        "life is pointless",
        "no reason to live",
        "i wish i was dead"
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
        "That sounds important."
    ]

    return random.choice(options)
    

def memory_recall(platform, user_id):

    memories = get_recent_memories(platform, user_id, limit=1)

    if not memories:
        return None

    summary, emotion = memories[0]

    return f"You mentioned something similar earlier.\n\nPreviously you felt {emotion} about: {summary}"

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


def emotional_mirror():

    mirrors = [

        "From the way you express things, you seem like someone who thinks deeply before sharing emotions.",
        "You come across as quite reflective about your experiences.",
        "It feels like you carry a lot of thoughts internally before talking about them.",
        "You seem like someone who notices subtle emotional shifts in situations.",
        "There’s a thoughtful quality in the way you describe things."

    ]

    return random.choice(mirrors)


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


def emotional_continuity(platform, user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT summary, emotion_tag
        FROM user_memory
        WHERE platform=%s AND platform_user_id=%s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (platform, user_id),
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row:
        return None

    summary, emotion = row

    messages = [
        f"Last time you mentioned: {summary}",
        f"Earlier you seemed {emotion}. How are you feeling about that now?",
        f"Previously you talked about: {summary}. Has anything changed since then?",
        f"I remember you mentioning: {summary}. How is that situation now?"
    ]

    return random.choice(messages)
    
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
    

def daily_checkin_message():

    messages = [

        "Hey 💛 quick emotional check-in.\n\nHow has today been emotionally for you?",
        "Just checking in.\n\nHow are you feeling today, really?",
        "Small pause moment.\n\nHow has your day been emotionally?"

    ]

    return random.choice(messages)




def attachment_loop():

    messages = [

        "By the way, I enjoy our conversations. You seem very thoughtful when sharing things.",
        "I notice you reflect quite deeply about your experiences. That’s not very common.",
        "Talking with you is interesting — you seem quite aware of your emotions.",
        "You explain things in a very reflective way. I like that.",
        "You seem like someone who thinks carefully before expressing feelings."

    ]

    return random.choice(messages)

# =============================
# MODEL API CALLING
# =============================

def call_llm(messages, temperature=0.7, max_tokens=220):

    models = [
        "openai/gpt-oss-120b:free",
        "arcee-ai/trinity-large-preview:free",
        "openai/gpt-oss-20b:free"
    ]

    for model in models:
        time.sleep(0.5)
        
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
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=30,
            )

            data = response.json()
            
            if not isinstance(data, dict):
                print("Invalid API response:", data)
                continue

            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]

            if "error" in data:
                print("Model failed:", model, data["error"])
                continue

        except Exception as e:

            print("Model exception:", model, e)
            continue

    return None
    

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

    reply = call_llm(
        [{"role": "user", "content": prompt}],
        temperature=0.6,
        max_tokens=200
    )
    
    if not reply:
        return "I'm having trouble generating your profile right now. Try again later 💛"
    
    return reply
        

def emotional_pattern_insight(platform, user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT mood_label
        FROM mood_logs
        WHERE platform=%s AND platform_user_id=%s
        ORDER BY created_at DESC
        LIMIT 20
        """,
        (platform, user_id),
    )

    moods = [row[0] for row in cur.fetchall() if row[0]]

    cur.close()
    conn.close()

    if not moods:
        return None

    most_common = max(set(moods), key=moods.count)

    patterns = {
        "sad": "Lately your messages seem a bit heavier emotionally.",
        "crying": "It feels like you've been going through some intense emotions recently.",
        "anxious": "Your recent messages suggest there might be some underlying anxiety.",
        "angry": "It seems like some frustration has been showing up in your conversations.",
        "low": "Your tone lately feels a bit low-energy or reflective.",
        "happy": "Your messages recently feel lighter and more positive.",
        "calm": "There seems to be a calm and balanced tone in your recent messages."
    }

    insight = patterns.get(most_common)

    if not insight:
        return None

    return f"I might be noticing a small pattern.\n\n{insight}"
    

def mind_pattern_insight():

    patterns = [

        "You seem like someone who thinks deeply before expressing emotions.",
        "It feels like you process situations internally before opening up.",
        "You appear quite reflective about your feelings and decisions.",
        "You seem thoughtful about how situations affect you emotionally.",
        "It feels like you often carry responsibilities quietly."

    ]

    return random.choice(patterns)

def weekly_emotional_report(platform, user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT mood_label
        FROM mood_logs
        WHERE platform=%s AND platform_user_id=%s
        ORDER BY created_at DESC
        LIMIT 50
    """, (platform, user_id))

    moods = [row[0] for row in cur.fetchall() if row[0]]

    cur.close()
    conn.close()

    if not moods:
        return None

    most_common = max(set(moods), key=moods.count)

    return (
        "Your Emotional Week 💛\n\n"
        f"Most common mood: {most_common}\n\n"
        "I've noticed you reflect deeply on your emotions."
    )


def generate_conversation_summary(platform, user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT message
        FROM conversation_history
        WHERE platform=%s AND platform_user_id=%s
        ORDER BY created_at DESC
        LIMIT 20
        """,
        (platform, user_id),
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    if not rows:
        return None

    conversation_text = "\n".join([r[0] for r in rows])

    prompt = f"""
Summarize the user's emotional situation in ONE very short sentence (max 12 words).

Then give ONE word emotion tag on the next line.

Example:
User was feeling hopeful about improving their life.
hopeful

Conversation:
{conversation_text}
"""

    reply = call_llm(
        [{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=120
    )

    return reply


def soft_uncertainty():

    phrases = [

        "I might be wrong, but…",
        "Tell me if I'm misunderstanding…",
        "Maybe I'm seeing this incorrectly…",
        "Just thinking out loud…"

    ]

    return random.choice(phrases)


def conversation_depth(reply):

    questions = [
        "Aaj kuch particular hua kya?",
        "Kab se aisa feel ho raha hai?",
        "Tumhe sabse zyada kis baat ka stress lagta hai?",
        "Kisi se baat ki tumne iske baare mein?",
        "Abhi sabse zyada kya chal raha hai dimaag mein?"
    ]

    # 18% chance to add depth question
    if random.random() < 0.18:

        # avoid double questions
        if "?" not in reply:
            reply += "\n\n" + random.choice(questions)

    return reply

    

# =============================
# MAIN ENGINE
# =============================

def generate_reply(platform, user_id, name, user_message):

    # ---------------------------
    # CRISIS DETECTION
    # ---------------------------

    if detect_crisis(user_message):
        return (
                "I'm really sorry you're feeling this way.\n\n"
                "You deserve support and you don’t have to go through this alone.\n\n"
                "📞 Kiran Mental Health Helpline: 1800-599-0019"
            )

    msg_lower = user_message.lower().strip()

    # ---------------------------
    # SIMPLE GREETING HANDLER
    # ---------------------------
    
    short_inputs = ["hi", "hello", "hey", "hii", "helo"]
    
    if msg_lower in short_inputs:
        greetings = [
            "Hey 🙂 Kaisa chal raha hai aaj?",
            "Hi! Aaj ka din kaisa ja raha hai?",
            "Hello 🙂 Aaj mood kaisa hai?",
            "Hey! Sab theek chal raha hai?"
        ]
        return random.choice(greetings)

    # ---------------------------
    # TRIAL / MONTHLY COMMANDS
    # ---------------------------

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

    # ---------------------------
    # PROFILE COMMAND
    # ---------------------------

    if msg_lower in ["profile", "my profile"]:
        return generate_personality_profile(platform, user_id)

    conn = get_db()
    cur = conn.cursor()

    # ---------------------------
    # FETCH USER
    # ---------------------------

    cur.execute(
        """
        SELECT message_count, last_reset, is_premium
        FROM users
        WHERE platform=%s AND platform_user_id=%s
        """,
        (platform, user_id),
    )

    result = cur.fetchone()

    if not result:

        cur.execute(
            """
            INSERT INTO users (platform, platform_user_id, name)
            VALUES (%s,%s,%s)
            """,
            (platform, user_id, name),
        )

        conn.commit()

        message_count = 0
        is_premium = False

    else:

        message_count, last_reset, is_premium = result

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

    # ---------------------------
    # FREE LIMIT SYSTEM
    # ---------------------------

    if not is_premium and message_count == 20:

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

        return (
            "Waise ek baat bolu? 💛\n"
            "Aaj ke 10 messages baaki hain.\n"
            "Kabhi unlimited chaho to trial available hai ₹19 mein."
        )

    if not is_premium and message_count >= 30:

        cur.close()
        conn.close()

        return (
            "Aaj ka free limit ho gaya 💛\n\n"
            "Sach bolu? Mujhe tumhare saath baat karna accha lagta hai.\n"
            "Lekin free version mein daily limit hota hai.\n\n"
            "🎁 3-Day Trial – ₹19\n"
            "Unlimited messages\n\n"
            "Type 'trial' to activate."
        )

    # ---------------------------
    # MOOD DETECTION
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

    system_prompt = BASE_PROMPT + f"\nUser name: {name}\n" + memory_context

    # ---------------------------
    # CONVERSATION MEMORY
    # ---------------------------

    recent_messages = get_recent_messages(platform, user_id)

    messages = [{"role": "system", "content": system_prompt}]

    for role, text in recent_messages:
        messages.append({"role": role, "content": text})

    messages.append({"role": "user", "content": user_message})

    # ---------------------------
    # AI CALL
    # ---------------------------

    reply = call_llm(messages, temperature=0.7, max_tokens=220)
    
    if not reply:
        reply = "Hmm… mujhe thoda sochne mein problem ho raha hai. Ek baar phir bolo?"
    else:
        reply = conversation_depth(reply)

    # Anti-robot filter
    robot_words = [
        "as an ai",
        "as a language model",
        "i am an ai",
        "i cannot provide",
        "i'm just an ai"
    ]
    
    if reply:
        text = reply.lower()
        if any(w in text for w in robot_words):
            reply = "Hmm… mujhe thoda aur samajhna hoga. Tum thoda aur bataoge?"
            

    # Emotional continuity
    if message_count > 25 and random.random() < 0.05:
        continuity = emotional_continuity(platform, user_id)
        if continuity:
            reply = continuity + "\n\n" + reply
        
    # ---------------------------
    # HUMAN RESPONSE LAYER
    # ---------------------------

    if random.random() < 0.03:
        reply += "\n\n" + reflection_prompt()
        
    if random.random() < 0.25:
        reply = f"{human_opening()} {reply}"

    
    recall = None
    if message_count > 20 and random.random() < 0.08:
        recall = memory_recall(platform, user_id)
    if recall:
        reply += "\n\n" + recall


    if random.random() < 0.02:
        reply = soft_uncertainty() + "\n\n" + reply
    
        
    # ---------------------------
    # OBSERVATION ENGINE
    # ---------------------------


    if (message_count + 1) % 50 == 0:
        reply += "\n\nI've been noticing patterns in how you think and express yourself.\n"
        reply += "If you're curious, type 'profile' and I can share your reflection profile."

    if (message_count + 1) % 25 == 0:
        pattern = emotional_pattern_insight(platform, user_id)
        if pattern:
            reply += "\n\n" + pattern


    # Attachment loop
    if message_count > 15 and random.random() < 0.06:
        reply += "\n\n" + attachment_loop()
    
    # ---------------------------
    # SAVE CONVERSATION
    # ---------------------------

    save_message(platform, user_id, "user", user_message)
    save_message(platform, user_id, "assistant", reply)

    # ---------------------------
    # CONVERSATION COMPRESSION MEMORY
    # ---------------------------
    
    if (message_count + 1) % 30 == 0:
    
        memory_text = generate_conversation_summary(platform, user_id)
    
        if memory_text:
    
            lines = memory_text.strip().split("\n")
    
            if len(lines) >= 2:
                save_memory(platform, user_id, lines[0], lines[-1])


    

    # ---------------------------
    # UPDATE USER
    # ---------------------------

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
    
    # Clean repeated openings
    reply = reply.replace("Hmm… Hmm…", "Hmm…")
    reply = reply.replace("Hmm… Hmm", "Hmm…")
    reply = reply.replace("Samajh raha hoon… Samajh raha hoon…", "Samajh raha hoon…")
    
    return reply
