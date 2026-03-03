from flask import Flask
import threading
import os

from config import CHANNEL
from db import init_db

app = Flask(__name__)

init_db()

# -----------------------------
# Health check route
# -----------------------------
@app.route("/")
def home():
    return "Maya backend running", 200

# -----------------------------
# Razorpay Webhook Route
# -----------------------------
@app.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():
    return "Webhook received", 200


# -----------------------------
# Start Bot in Background Thread
# -----------------------------
def start_bot():
    if CHANNEL == "telegram":
        from telegram_bot import start
        start()
    elif CHANNEL == "whatsapp":
        from whatsapp_webhook import start
        start()


if __name__ == "__main__":
    threading.Thread(target=start_bot).start()

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
