from core.config import CHANNEL
from core.db import init_db

init_db()

if CHANNEL == "telegram":
    from channels.telegram_bot import start
    start()

elif CHANNEL == "whatsapp":
    from channels.whatsapp_webhook import start
    start()
