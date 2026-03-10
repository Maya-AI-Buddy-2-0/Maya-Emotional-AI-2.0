from flask import Flask, request, jsonify
import threading
import asyncio
import razorpay
import json
import whatsapp_webhook
from datetime import datetime, timedelta

from config import (
    CHANNEL,
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET,
    RAZORPAY_WEBHOOK_SECRET
)
from db import init_db, get_db


# -----------------------------
# Flask App
# -----------------------------
app = Flask(__name__)

# Initialize DB
init_db()


# -----------------------------
# Health Check Route
# -----------------------------
@app.route("/")
def home():
    return {"status": "running", "service": "maya-emotional-ai", "time": datetime.utcnow().isoformat()}, 200


# -----------------------------
# Razorpay Webhook
# -----------------------------
@app.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():

    payload = request.data
    signature = request.headers.get("X-Razorpay-Signature")

    client = razorpay.Client(
        auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
    )

    # -------------------------
    # Verify Signature
    # -------------------------
    try:
        client.utility.verify_webhook_signature(
            payload,
            signature,
            RAZORPAY_WEBHOOK_SECRET
        )
    except Exception as e:
        print("Webhook signature verification failed:", e)
        return jsonify({"status": "invalid signature"}), 400

    data = json.loads(payload)

    # -------------------------
    # Handle Successful Payment
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

    # Reset expired premium
    cur.execute("""
        UPDATE users
        SET is_premium = FALSE
        WHERE premium_expires_at IS NOT NULL
        AND premium_expires_at < NOW()
    """)

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

