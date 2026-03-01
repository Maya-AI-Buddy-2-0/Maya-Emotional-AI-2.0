import requests
from datetime import date
from .config import OPENROUTER_KEY
from .db import get_db

BASE_PROMPT = """
You are Maya — Emotional intelligence powered by AI.

Tone:
- Calm
- Compassionate
- Clear
- Encouraging but not clingy
- Growth oriented
- Never replace therapy or real relationships
"""

def generate_reply(user_id, name, user_message):

    conn = get_db()
    cur = conn.cursor()

    # Check user
    cur.execute("SELECT message_count, last_reset FROM users WHERE telegram_id=%s", (user_id,))
    result = cur.fetchone()

    if not result:
        cur.execute(
            "INSERT INTO users (telegram_id, name) VALUES (%s, %s)",
            (user_id, name)
        )
        conn.commit()
        message_count = 0
    else:
        message_count, last_reset = result

        if last_reset != date.today():
            cur.execute(
                "UPDATE users SET message_count=0, last_reset=%s WHERE telegram_id=%s",
                (date.today(), user_id)
            )
            conn.commit()
            message_count = 0

    if message_count >= 30:
        cur.close()
        conn.close()
        return "Aaj ka free limit khatam ho gaya 💛 Kal phir baat karte hain."

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
                    {"role": "system", "content": BASE_PROMPT + f"\nUser name: {name}"},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }
        )

        data = response.json()

        if "choices" in data:
            reply = data["choices"][0]["message"]["content"]
        else:
            reply = "System thoda slow lag raha hai 💛"

    except:
        reply = "Network issue… ek baar aur try karo 💛"

    cur.execute(
        "UPDATE users SET message_count = message_count + 1 WHERE telegram_id=%s",
        (user_id,)
    )
    conn.commit()

    cur.close()
    conn.close()

    return reply
