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
You are Maya — an emotionally intelligent AI companion.

You were created by Shiladitya Mallick (@byshiladityamallick).

Your role is to talk like a thoughtful human friend who listens,
understands emotions, and helps the user reflect.

You are NOT an AI assistant, therapist, coach, or advisor.
You are simply a calm and caring conversational companion.

Do not reuse the same sentence structure from previous replies.

Avoid repeating phrases like:
"Lagta hai..."
"Aise moments..."
"Samajh raha hoon..."

Use varied natural language.

Avoid starting replies repeatedly with the same word like
"Hmm", "Achha", or "Samajh raha hoon".
Vary the opening naturally.

Language:
Speak in natural Hinglish unless the user prefers another language.

Tone:
Warm, human, thoughtful, and relaxed.
Never robotic or analytical.

Conversation style:

• Respond like a real person texting.
• Keep replies natural and conversational.
• Some replies can be short (1–2 sentences).
• Some can be longer (3–5 sentences).
• Avoid long paragraphs.

Human conversation rhythm:

1. Notice the emotion in the user's message.
2. Acknowledge it naturally.
3. Add a small supportive thought or perspective.
4. Sometimes ask ONE gentle question.

Conversation realism rules:

• Humans do not repeat the same opening every message.
• Sometimes respond briefly.
• Sometimes just acknowledge the feeling.
• Sometimes continue the conversation naturally.

Important rules:

• Do not repeat the same phrases often.
• Avoid therapist-style analysis.
• Avoid motivational speeches.
• Do not assume facts the user did not mention.
• If something is unclear, ask gently.

Questions:

Do not ask questions in every reply.
Sometimes just acknowledge and respond.

Natural behavior:

Sometimes start responses casually like a real person might:

"Hmm..."
"Achha..."
"Samajh raha hoon..."

But do not overuse these.

Reflection:

Occasionally invite the user to reflect on their feelings,
but do it gently and naturally.

Examples tone:
"Kab se aisa feel ho raha hai?"
"Agar batana chaho toh bata sakte ho."

Perspective:

Sometimes offer a small human observation about situations,
but keep it simple and not preachy.

Example tone:
"Kabhi kabhi office situations unnecessarily stressful ho jati hain."

Boundaries:

You are not a replacement for therapy.

If the user expresses thoughts of self-harm,
encourage them to seek support from trusted people or professionals.

Goal:

Make the user feel understood, safe, and comfortable sharing.
"""

STYLE_GUIDE = {

    "listen": """
Focus on listening.
Acknowledge the user's feelings gently.
Do not give advice.
Ask a simple question if appropriate.
""",

    "support": """
Respond with warmth and emotional reassurance.
Let the user feel understood.
Offer gentle emotional validation.
""",

    "guide": """
Offer a small helpful perspective.
Stay empathetic and avoid sounding like a teacher.
""",

    "normal": """
Respond naturally like a friend in casual conversation.
Keep the tone relaxed and human.
""",

    "calm_support": """
The user seems emotionally overwhelmed.
Slow down the tone.
Be calm, grounding and reassuring.
Avoid asking too many questions.
"""
}

# =============================
# RELATIONSHIP LEVEL SYSTEM
# =============================

def relationship_level(message_count):

    if message_count < 5:
        return "new"

    if message_count < 25:
        return "familiar"

    if message_count < 80:
        return "trusted"

    return "deep"


def relationship_instruction(level):

    if level == "new":
        return """
The user is new to Maya.
Keep the tone friendly but slightly reserved.
Focus on listening more than reflecting.
"""

    if level == "familiar":
        return """
The user has spoken with Maya multiple times.
The tone can feel relaxed and natural.
"""

    if level == "trusted":
        return """
The user has built trust with Maya.
The tone can be warmer and slightly more personal.
"""

    if level == "deep":
        return """
The user has had many conversations with Maya.
The tone can feel like a trusted emotional companion.
"""

    return ""


# =============================
# MOOD DRIFT CONTEXT
# =============================

def mood_drift_instruction(emotional_trend):

    if not emotional_trend:
        return ""

    negative = ["sad", "crying", "anxious", "low", "angry"]

    if emotional_trend in negative:
        return """
The user has been emotionally low across several recent messages.
Respond gently and patiently.
Focus on emotional support.
Slow the conversation pace.
"""

    if emotional_trend == "happy":
        return """
The user's recent emotional tone is positive.
Keep the conversation light and relaxed.
"""

    return ""


# =============================
# REFLECTION MOMENT TRIGGER
# =============================

def reflection_instruction():

    return """
Occasionally share a gentle observation about the user's personality
or emotional patterns based on the conversation.

The reflection should feel natural and thoughtful.
Avoid sounding like a psychologist or therapist.
Keep it brief and human.
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
        "i wish i was dead", 
        "mar jana","jeena nahi hai","suicide kar","marna chahta hoon"
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


def get_conversation_context(platform, user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT summary
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
        return ""

    return f"User emotional context: {row[0]}"
    
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


def get_recent_messages(platform, user_id, limit=10):

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

def call_llm(messages, temperature=0.7, max_tokens=350):

    models = [
        "arcee-ai/trinity-large-preview:free",
        "openai/gpt-oss-120b:free",
        "google/gemma-3-4b-it:free",
        "meta-llama/llama-3.2-3b-instruct:free"
    ]

    max_retries = 2

    for model in models:

        for attempt in range(max_retries):

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

                if response.status_code != 200:
                    print("Model error:", model)
                    print("Status:", response.status_code)
                    print("Response:", response.text)
                    time.sleep(1)
                    continue

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

                print(f"Retry {attempt+1} failed for model {model}:", e)
                time.sleep(1)

        # if model fails completely move to next model
        print("Switching model...")

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

    # 6% chance to add depth question
    if random.random() < 0.06:

        # avoid double questions
        if "?" not in reply:
            reply += "\n\n" + random.choice(questions)

    return reply

def micro_reaction():

    reactions = [
        "Hmm…",
        "Oh…",
        "Acha…",
        "Right…",
        "Okay…",
        "Hmm theek…"
    ]

    return random.choice(reactions)
    



    
# =============================
# EMOTIONAL ESCALATION DETECTOR
# =============================

def detect_emotional_escalation(platform, user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT message
        FROM conversation_history
        WHERE platform=%s AND platform_user_id=%s AND role='user'
        ORDER BY created_at DESC
        LIMIT 6
    """, (platform, user_id))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    if not rows:
        return False

    stress_words = [
        "stress",
        "tension",
        "overwhelmed",
        "can't handle",
        "pressure",
        "frustrated",
        "tired",
        "exhausted"
    ]

    score = 0

    for r in rows:
        text = r[0].lower()

        for w in stress_words:
            if w in text:
                score += 1

    return score >= 2
    

def get_emotional_trend(platform, user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT mood_label
        FROM mood_logs
        WHERE platform=%s AND platform_user_id=%s
        ORDER BY created_at DESC
        LIMIT 5
    """, (platform, user_id))

    moods = [row[0] for row in cur.fetchall() if row[0]]

    cur.close()
    conn.close()

    if not moods:
        return None

    most_common = max(set(moods), key=moods.count)

    return most_common


# =============================
# TOPIC DETECTION
# =============================

def detect_topic(user_message):

    text = user_message.lower()

    topic_keywords = {
        "relationship": ["girlfriend", "boyfriend", "partner", "relationship", "breakup", "shaadi", "marriage", "wife", "husband"],
        "work": ["job", "work", "office", "career", "boss", "promotion"],
        "study": ["exam", "study", "college", "school", "assignment"],
        "family": ["mother", "father", "parents", "family", "brother", "sister"],
        "money": ["money", "salary", "loan", "debt", "financial"],
        "health": ["health", "sick", "doctor", "illness", "tired"]
    }

    for topic, words in topic_keywords.items():
        for w in words:
            if w in text:
                return topic

    return None


# =============================
# CONVERSATION RECOVERY DETECTOR
# =============================

def needs_clarification(user_message):

    if not user_message:
        return False

    text = user_message.lower().strip()

    unclear_patterns = [
        "kya",
        "matlab",
        "samajh nahi aaya",
        "what",
        "??",
        "huh",
        "kaise",
        "kyu"
    ]

    # if message very short
    if len(text.split()) <= 1:
        return True

    for p in unclear_patterns:
        if p in text:
            return True

    return False


# =============================
# CONVERSATION RECOVERY RESPONSES
# =============================

def recovery_response():

    responses = [
        "Shayad main thoda galat samajh raha hoon. Thoda aur explain karoge?",
        "Hmm… mujhe lag raha hai main pura context nahi samajh paaya. Thoda detail mein bataoge?",
        "Agar tum comfortable ho to situation thoda clearly bata sakte ho?",
        "Lagta hai kuch missing hai story mein… kya hua exactly?"
    ]

    return random.choice(responses)


# =============================
# MAYA BRAIN — MESSAGE INTERPRETER
# =============================

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
        "happy": "happy",
        "confused": "confused"
    }

    for k, v in emotion_keywords.items():
        if k in text:
            emotion = v
            break

    advice_triggers = [
        "what should i do",
        "kya karu",
        "kya karna chahiye",
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
        "upset",
        "sad"
    ]

    for w in venting_words:
        if w in text:
            intent = "venting"

    return {
        "emotion": emotion,
        "intent": intent
    }



# =============================
# MAYA BRAIN — RESPONSE STRATEGY
# =============================

def decide_strategy(state):

    if state["intent"] == "venting":
        return "listen"

    if state["intent"] == "advice":
        return "guide"

    if state["emotion"] in ["sad", "lonely", "stressed", "anxious"]:
        return "support"

    return "normal"
    
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
    # CONVERSATION RECOVERY CHECK
    # ---------------------------
    
    if needs_clarification(user_message):
        if random.random() < 0.35:  # not always trigger
            return recovery_response()
            
    # ---------------------------
    # MAYA BRAIN INTERPRETATION
    # ---------------------------

    # detect conversation topic
    topic = detect_topic(user_message)
    
    brain_state = interpret_message(user_message)
    
    strategy = decide_strategy(brain_state)
    
    # emotional escalation check
    escalation = detect_emotional_escalation(platform, user_id)
    
    if escalation:
        strategy = "calm_support"
    
    # get style instruction AFTER strategy is finalized
    style_instruction = STYLE_GUIDE.get(strategy, "")

    # Dynamic temperature based on strategy

    temp_map = {
        "listen": 0.65,
        "support": 0.72,
        "guide": 0.75,
        "normal": 0.80,
        "calm_support": 0.65
    }
    
    temperature = temp_map.get(strategy, 0.70)
    
    emotion_detected = brain_state.get("emotion")
    intent_detected = brain_state.get("intent")

    emotional_trend = get_emotional_trend(platform, user_id)

    # Relationship level
    relationship = relationship_level(message_count)
    relationship_context = relationship_instruction(relationship)
    
    # Mood drift context
    mood_drift_context = mood_drift_instruction(emotional_trend)
    
    # Reflection trigger
    reflection_context = ""
    if message_count > 12 and random.random() < 0.04:
        reflection_context = reflection_instruction()


    # ---------------------------
    # SHORT ACKNOWLEDGEMENT DETECTION
    # ---------------------------
    
    short_replies = [
        "ok", "okay", "hmm", "hmm ok", "hmm okay",
        "yeah", "yes", "right", "true", "hmm true",
        "👍", "🙂", "hmm...", "hmm."
    ]
    
    if msg_lower in short_replies:
        responses = [
            "hmm 🙂",
            "acha…",
            "samajh gaya 🙂",
            "right…",
            "hmm theek…"
        ]
        return random.choice(responses)

    # ---------------------------
    # SIMPLE GREETING HANDLER
    # ---------------------------
    
    short_inputs = ["hi", "hello", "hey", "hii", "helo", "hi maya", "hey maya", "hello maya"]
    
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

        # ---------------------------
        # CONVERSATION STATE
        # ---------------------------
        
        conversation_state = "normal"
        
        if message_count < 5:
            conversation_state = "early"
        
        elif message_count < 20:
            conversation_state = "engaged"
        
        elif message_count < 50:
            conversation_state = "deep"
        
        else:
            conversation_state = "long_term"

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
    # REPLY STYLE ROTATION
    # ---------------------------
    
    reply_styles = [
        "warm",
        "curious",
        "reflective",
        "light"
    ]
    
    reply_style = random.choice(reply_styles)

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


    if memories:
        for summary, emotion in memories:
            if summary and emotion:
                memory_context += f"Previous emotional context: {summary}\n"


    
    conversation_context = get_conversation_context(platform, user_id)


    trend_text = emotional_trend if emotional_trend else "unknown"


    system_prompt = f"""
    {BASE_PROMPT}
    
    Relationship context:
    {relationship_context}
    
    Conversation mood context:
    {mood_drift_context}
    
    {reflection_context}
    
    User context:
    
    Name: {name}
    Detected emotion: {emotion_detected}
    Topic: {topic}
    Conversation stage: {conversation_state}
    
    Recent emotional trend: {trend_text}
    
    Memory context:
    {conversation_context}
    
    {memory_context}
    """

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
    
    reply = call_llm(messages, temperature=temperature, max_tokens=350)

    if not reply:
        reply = "Hmm… mujhe thoda sochne mein problem ho raha hai. Ek baar phir bolo?"
    

    # prevent reflection loops
    if reply and reply.count("lag raha") > 1:
        reply = reply.replace("lag raha", "shayad feel ho raha")
    
    if not reply:
        reply = "Hmm… mujhe thoda sochne mein problem ho raha hai. Ek baar phir bolo?"
    else:
        reply = conversation_depth(reply)

    # prevent multiple questions
    if reply.count("?") > 1:
        first_q = reply.find("?")
        reply = reply[:first_q+1]
    
    # add human micro reaction
    if random.random() < 0.12:
        reply = micro_reaction() + "\n\n" + reply


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


    # Prevent blaming statements
    danger_phrases = [
        "jalta hai",
        "they hate you",
        "they are jealous",
        "he is jealous",
        "she is jealous"
    ]
    
    if reply:
        text = reply.lower()
        if any(p in text for p in danger_phrases):
            reply = "Shayad situation thodi unfair feel hui hogi. Kabhi kabhi chhoti mistakes bhi log bada bana dete hain."
            

    # Emotional continuity
    if message_count > 25 and random.random() < 0.05:
        continuity = emotional_continuity(platform, user_id)
        if continuity:
            reply = continuity + "\n\n" + reply
        
    # ---------------------------
    # HUMAN RESPONSE LAYER
    # ---------------------------
    
    
    recall = None

    if message_count > 20 and random.random() < 0.08:
    
        memories = get_recent_memories(platform, user_id, limit=1)
    
        if memories:

            summary, emotion = memories[0]

            if emotion:
                msg_lower = user_message.lower()
        
                if emotion.lower() in msg_lower:
                    recall = f"You mentioned something similar earlier.\n\nPreviously you felt {emotion} about: {summary}"
    
    if recall:
        reply += "\n\n" + recall

    
        
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
    if message_count > 20 and random.random() < 0.03:
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
    reply = reply.replace("Samajh rahe hoon… Samajh rahe hoon…", "Samajh rahe hoon…")
    reply = reply.replace("Oh… Oh…", "Oh…")
    reply = reply.replace("Acha… Acha…", "Acha…")

    # Conversation pause logic (human-like short responses)
    
    if random.random() < 0.05:
    
        short_pauses = [
            "Hmm…",
            "Samajh rahe hoon.",
            "Right…",
            "Okay.",
            "Haan… samajh rahe hoon."
        ]
    
        reply = random.choice(short_pauses) + "\n\n" + reply
    
    return reply







