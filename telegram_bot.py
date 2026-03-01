from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from telegram import Update
from core.config import BOT_TOKEN
from core.maya_engine import generate_reply

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    name = update.message.from_user.first_name
    text = update.message.text

    reply = generate_reply(user_id, name, text)

    await update.message.reply_text(reply)

def start():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Telegram running...")
    app.run_polling()
