from config import CHANNEL
from db import init_db

init_db()

if CHANNEL == "telegram":
    from telegram_bot import start
    start()

elif CHANNEL == "whatsapp":
    from whatsapp_webhook import start
    start()
