from flask import Flask, request, jsonify
import threading
import asyncio
import os
import razorpay
import json
from datetime import datetime, timedelta

from config import CHANNEL
from db import init_db, get_db

# -----------------------------
# Flask App
# -----------------------------
app = Flask(__name__)

# Initialize DB
init_db()

# -----------------------------
# Home Route (Health Check)
# -----------------------------
@app.route("/")
def home():
    return "Maya backend running", 200


# -----------------------------
# Razorpay Webhook
# -----------------------------
WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

@app.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():

    payload = request.data
    signature = request.headers.get("X-Razorpay-Signature")

    client = razorpay.Client(
        auth=(
            os.getenv("RAZORPAY_KEY_ID"),
            os.getenv("RAZORPAY_KEY_SECRET")
        )
    )

    # -------------------------
    # Verify Razorpay Signature
    # -------------------------
    try:
        client.utility.verify_webhook_signature(
            payload,
            signature,
            WEBHOOK_SECRET
        )
    except Exception as e:
        print("Webhook signature verification failed:", e)
        return jsonify({"status": "invalid signature"}), 400

    data = json.loads(payload)

    # -------------------------
    # Handle Payment Success
    # -------------------------
    if data.get("event") == "payment_link.paid":

        entity = data["payload"]["payment_link"]["entity"]
        notes = entity.get("notes", {})

        platform = notes.get("platform")
        user_id = notes.get("platform_user_id")
        plan = notes.get("plan")

        if platform and user_id and plan:
            activate_subscription(platform, user_id, plan)

    return jsonify({"status": "ok"}), 200


# -----------------------------
# Activate Subscription
# -----------------------------
def activate_subscription(platform, user_id, plan):

    conn = get_db()
    cur = conn.cursor()

    if plan == "trial":
        expires = datetime.utcnow() + timedelta(days=3)
        subscription_type = "trial"
    else:
        expires = datetime.utcnow() + timedelta(days=30)
        subscription_type = "monthly"

    cur.execute("""
        UPDATE users
        SET is_premium = TRUE,
            subscription_type = %s,
            premium_expires_at = %s,
            trial_used = CASE 
                WHEN %s = 'trial' THEN TRUE
                ELSE trial_used
            END,
            trial_expiry_notified = FALSE
        WHERE platform = %s
        AND platform_user_id = %s
    """, (subscription_type, expires, subscription_type, platform, user_id))

    conn.commit()
    cur.close()
    conn.close()

    print(f"Subscription activated for {user_id} ({subscription_type})")

# -----------------------------
# Start Bot in Background
# -----------------------------


def start_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if CHANNEL == "telegram":
        from telegram_bot import start
        loop.run_until_complete(start())
    elif CHANNEL == "whatsapp":
        from whatsapp_webhook import start
        start()


# Start bot in background when module loads
threading.Thread(target=start_bot, daemon=True).start()
