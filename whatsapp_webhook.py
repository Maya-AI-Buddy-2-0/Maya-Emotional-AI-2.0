import requests
import random
import time
import logging

from flask import request, jsonify

from config import WHATSAPP_VERIFY_TOKEN, WHATSAPP_TOKEN, PHONE_NUMBER_ID
from maya_engine import generate_reply


logging.basicConfig(level=logging.INFO)


def send_whatsapp_message(user_id, message):

    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": user_id,
        "type": "text",
        "text": {"body": message}
    }

    requests.post(url, headers=headers, json=payload)


def parse_whatsapp_message(data):

    try:

        entry = data["entry"][0]
        change = entry["changes"][0]
        value = change["value"]

        if "messages" not in value:
            return None, None, None

        message = value["messages"][0]

        user_id = message["from"]
        message_type = message.get("type")

        text = None

        if message_type == "text":
            text = message["text"]["body"]

        elif message_type == "button":
            text = message["button"]["text"]

        elif message_type == "interactive":

            interactive = message["interactive"]

            if interactive["type"] == "button_reply":
                text = interactive["button_reply"]["title"]

            elif interactive["type"] == "list_reply":
                text = interactive["list_reply"]["title"]

        elif message_type == "image":
            text = message["image"].get("caption", "image")

        if not text:
            text = "..."

        return user_id, "User", text

    except Exception as e:

        logging.error("Parsing error: %s", e)
        return None, None, None


# ---------------------------------
# REGISTER ROUTES FUNCTION
# ---------------------------------

def register_whatsapp_routes(app):

    @app.route("/webhook", methods=["GET"])
    def verify_whatsapp():

        verify_token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if verify_token == WHATSAPP_VERIFY_TOKEN:
            return challenge, 200

        return "Verification failed", 403


    @app.route("/webhook", methods=["POST"])
    def receive_whatsapp():

        data = request.json

        user_id, name, message = parse_whatsapp_message(data)

        if not user_id:
            return jsonify({"status": "ignored"}), 200

        logging.info(f"WhatsApp message: {message}")

        try:

            reply = generate_reply(
                "whatsapp",
                user_id,
                name,
                message
            )

        except Exception as e:

            logging.error(e)
            reply = "Hmm… thoda issue aa gaya. Ek baar phir bolo?"

        time.sleep(random.uniform(1.5, 3.5))

        send_whatsapp_message(user_id, reply)

        return jsonify({"status": "ok"}), 200
