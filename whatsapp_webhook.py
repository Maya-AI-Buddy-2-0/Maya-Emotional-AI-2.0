from flask import Flask, request, jsonify
from core.config import WHATSAPP_VERIFY_TOKEN
from core.maya_engine import generate_reply

app = Flask(__name__)

@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == WHATSAPP_VERIFY_TOKEN:
        return challenge
    return "Verification failed"

@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.json

    # parse incoming WhatsApp data properly later
    # placeholder logic

    user_id = "whatsapp_user"
    name = "User"
    message = "Test message"

    reply = generate_reply(user_id, name, message)

    return jsonify({"status": "received"})
    
def start():
    print("WhatsApp webhook running...")
    app.run(host="0.0.0.0", port=5000)
