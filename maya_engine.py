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

Respond like a real person texting.
Avoid sounding like an AI assistant.
Use natural conversational language.
Short natural messages are better than perfect sentences.

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
• Never assume reasons for the user's feelings
• Do not repeat the same opening phrases
• Never invent situations that the user did not mention
• If the user says something simple like "hi", respond casually
• Do not continue imaginary conversations

Sometimes ask a gentle question.

Never say:
"As an AI"
"As a language model"
"""

# =====================================
# PERSONALITY STRATEGY
# =====================================

STYLE_GUIDE = {

    "listener": """
The user is sharing emotions.
Listen carefully.
Be warm and understanding.
Do not give advice immediately.
""",

    "support": """
User seems emotionally low.
Respond with reassurance and empathy.
Be calm and supportive.
""",

    "guide": """
User is asking for help.
Offer a thoughtful perspective.
Avoid sounding like a teacher.
""",

    "friend": """
Respond casually like a relaxed friend.
Keep tone natural and conversational.
"""
}

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
# MESSAGE INTERPRETATION
# =====================================

def interpret_message(user_message):

    text = user_message.lower()

    emotion = None
    intent = "conversation"

    emotion_keywords = {
        "stress": "stressed",
        "tension": "stressed",
        "sad": "sad",
        "lonely": "lonely",
        "anxious": "anxious",
        "angry": "angry",
        "happy": "happy"
    }

    for k, v in emotion_keywords.items():
        if k in text:
            emotion = v
            break

    advice_triggers = [
        "what should i do",
        "kya karu",
        "suggest",
        "help me decide"
    ]

    for trigger in advice_triggers:
        if trigger in text:
            intent = "advice"

    venting_words = [
        "stress",
        "tired",
        "frustrated",
        "upset"
    ]

    for w in venting_words:
        if w in text:
            intent = "venting"

    return {
        "emotion": emotion,
        "intent": intent
    }


def decide_strategy(state):

    if state["intent"] == "venting":
        return "listener"

    if state["intent"] == "advice":
        return "guide"

    if state["emotion"] in ["sad", "lonely", "stressed", "anxious"]:
        return "support"

    return "friend"



# =====================================
# DATABASE CHAT STORAGE
# =====================================

def save_message(platform, user_id, role, message):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO conversation_history
        (platform, platform_user_id, role, message)
        VALUES (%s,%s,%s,%s)
    """, (platform, user_id, role, message))

    conn.commit()
    cur.close()
    conn.close()


def get_recent_messages(platform, user_id, limit=8):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT role, message
        FROM conversation_history
        WHERE platform=%s AND platform_user_id=%s
        ORDER BY created_at DESC
        LIMIT %s
    """, (platform, user_id, limit))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return list(reversed(rows))


# =====================================
# LIFE MEMORY SYSTEM
# =====================================

def extract_user_memory(platform, user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT message
        FROM conversation_history
        WHERE platform=%s
        AND platform_user_id=%s
        AND role='user'
        ORDER BY created_at DESC
        LIMIT 12
    """, (platform, user_id))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    if not rows:
        return None

    conversation = "\n".join([r[0] for r in rows])

    prompt = f"""
Extract ONE stable life fact about the user.

Rules:
- max 12 words
- only long-term facts
- examples: job, exam, relationship, location
- if nothing useful reply NONE

Messages:
{conversation}
"""

    result = call_llm([{"role": "user", "content": prompt}])

    if not result:
        return None

    result = result.strip()

    if result.upper() == "NONE":
        return None

    return result


def save_user_memory(platform, user_id, summary):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO user_memory (platform, platform_user_id, summary)
        VALUES (%s,%s,%s)
    """, (platform, user_id, summary))

    conn.commit()
    cur.close()
    conn.close()


def get_user_memories(platform, user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT summary
        FROM user_memory
        WHERE platform=%s
        AND platform_user_id=%s
        ORDER BY created_at DESC
        LIMIT 6
    """, (platform, user_id))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [r[0] for r in rows]


# =====================================
# CONVERSATION COMPRESSION MEMORY
# =====================================

def generate_conversation_summary(platform, user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT message
        FROM conversation_history
        WHERE platform=%s
        AND platform_user_id=%s
        ORDER BY created_at DESC
        LIMIT 20
    """, (platform, user_id))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    if not rows:
        return None

    conversation = "\n".join([r[0] for r in rows])

    prompt = f"""
Summarize the user's situation in ONE short sentence.

Rules:
- max 12 words
- capture the core situation
- avoid emotional analysis

Examples:
User stressed about conflict with manager
User preparing for important exams
User worried about relationship problems

Conversation:
{conversation}
"""

    summary = call_llm([{"role": "user", "content": prompt}])

    return summary


# =====================================
# LLM CALL
# =====================================

def call_llm(messages):

    models = [
        "meta-llama/llama-3.2-3b-instruct:free",
        "arcee-ai/trinity-large-preview:free"    
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
                    "max_tokens": 220,
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
# DAILY CHECKIN GENERATOR
# =====================================

def daily_checkin_message():

    prompt = """
Write a short friendly daily emotional check-in message.

Rules:
- 1 or 2 sentences
- casual human tone
- feels like a friend texting
- not motivational speech
"""

    reply = call_llm([
        {"role": "user", "content": prompt}
    ])

    if not reply:
        reply = "Hey… just checking in. How’s your day going?"

    return reply


# =====================================
# LATE NIGHT CHECKIN GENERATOR
# =====================================

def late_night_checkin_message():

    prompt = """
Write a short late-night emotional check-in message.

Rules:
- calm tone
- 1 or 2 sentences
- feels like a friend texting late at night
"""

    reply = call_llm([
        {"role": "user", "content": prompt}
    ])

    if not reply:
        reply = "Still awake? Nights can feel quiet sometimes."

    return reply


# =====================================
# MAIN REPLY ENGINE
# =====================================

def generate_reply(platform, user_id, name, user_message):

    msg_lower = user_message.lower().strip()

    if detect_crisis(user_message):

        return (
            "I'm really sorry you're feeling this way.\n\n"
            "You deserve support and you don’t have to go through this alone.\n\n"
            "📞 Kiran Mental Health Helpline: 1800-599-0019"
        )


    

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


    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT message_count, last_reset, is_premium
        FROM users
        WHERE platform=%s AND platform_user_id=%s
    """, (platform, user_id))

    

    row = cur.fetchone()

    if not row:

        cur.execute("""
            INSERT INTO users (platform, platform_user_id, name, last_reset)
            VALUES (%s,%s,%s,%s)
        """, (platform, user_id, name, date.today()))

        conn.commit()

        message_count = 0
        is_premium = False

    else:

        message_count, last_reset, is_premium = row

        if last_reset != date.today():

            cur.execute("""
                UPDATE users
                SET message_count=0, last_reset=%s
                WHERE platform=%s AND platform_user_id=%s
            """, (date.today(), platform, user_id))

            conn.commit()

            message_count = 0
            

        greetings = ["hi", "hello", "hey", "hii"]
    
        if msg_lower.startswith(tuple(greetings)) and message_count == 0:
    
            return random.choice([
                "Hey 🙂 kaisa chal raha hai aaj?",
                "Hi! Aaj ka din kaisa ja raha hai?",
                "Hello 🙂 mood kaisa hai?"
            ])


    if not is_premium and message_count == 20:

        return (
            "Waise ek baat bolu? 💛\n"
            "Aaj ke 10 messages baaki hain.\n"
            "Kabhi unlimited chaho to 'trial' likh sakte ho."
        )


    if not is_premium and message_count >= 30:

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


    # =====================================
    # PERSONALITY CONTEXT
    # =====================================
    
    brain_state = interpret_message(user_message)
    
    strategy = decide_strategy(brain_state)
    
    style_instruction = STYLE_GUIDE.get(strategy, "")
    
    
    # =====================================
    # MEMORY CONTEXT
    # =====================================
    
    memories = get_user_memories(platform, user_id)
    recent_messages = get_recent_messages(platform, user_id)

    # =====================================
    # MEMORY CALLBACK (bring up past things)
    # =====================================
    
    memory_callback = ""
    
    if memories and random.random() < 0.18:   # ~18% chance
    
        memory = random.choice(memories)
    
        memory_prompt = f"""
    The user previously mentioned this fact:
    
    {memory}
    
    Write ONE short casual message checking on it.
    
    Rules:
    - sound natural
    - Hinglish
    - 1 sentence
    - like a friend remembering something
    """
    
        callback_reply = call_llm([
            {"role": "user", "content": memory_prompt}
        ])
    
        if callback_reply:
            memory_callback = callback_reply.strip()
    
    system_prompt = BASE_PROMPT + f"""
    Conversation mode:
    {strategy}
    
    Guideline:
    {style_instruction}
    
    {memory_block}
    
    Possible topic to casually bring up:
    {memory_callback}
    """

    reply_styles = [
        "Respond normally.",
        "Keep the reply very short.",
        "Respond casually like WhatsApp chat.",
        "Use a relaxed friendly tone.",
        "Sometimes use a small reaction like 'hmm', 'oh', 'acha'."
    ]
    
    style_modifier = random.choice(reply_styles)
    
    system_prompt = system_prompt + f"""
    
    Reply style instruction:
    {style_modifier}
    """

    messages = [{"role": "system", "content": system_prompt}]

    for role, text in recent_messages:
        messages.append({"role": role, "content": text})

    messages.append({"role": "user", "content": user_message})


    reply = call_llm(messages)
    
    # keep max 2 sentences
    reply = reply.split("\n")[0]
    if len(reply) > 220:
        reply = reply[:220]

    if not reply:
        reply = "Hmm… thoda network issue lag raha hai. Phir se bolo?"

    # remove repeated blank lines
    reply = "\n".join([l for l in reply.split("\n") if l.strip()])

    reply = reply.strip()

    # small human texting randomness
    if random.random() < 0.25:
        reply += random.choice([" 🙂", " hmm", " acha", " ya", " oh"])
        
    save_message(platform, user_id, "user", user_message)
    save_message(platform, user_id, "assistant", reply)


    # =====================================
    # LIFE MEMORY EXTRACTION
    # =====================================

    if random.random() < 0.08:

        memory = extract_user_memory(platform, user_id)

        if memory:
            save_user_memory(platform, user_id, memory)


    # =====================================
    # CONVERSATION COMPRESSION
    # =====================================

    if (message_count + 1) % 30 == 0:

        summary = generate_conversation_summary(platform, user_id)

        if summary:
            save_user_memory(platform, user_id, summary)


    cur.execute("""
        UPDATE users
        SET message_count = message_count + 1,
        last_active = NOW()
        WHERE platform=%s AND platform_user_id=%s
    """, (platform, user_id))

    conn.commit()

    cur.close()
    conn.close()

    return reply
