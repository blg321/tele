import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

# Load .env file
load_dotenv()

# ===== FLASK FOR KEEPING ALIVE =====
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "M0THB0T is alive and running!"

def run_flask():
    app_flask.run(host='0.0.0.0', port=10000)

# ===== BOT CONFIGURATION =====
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found! Create a .env file or set environment variable.")

# ===== COMMAND HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "🦋 *M0THB0T is online!*\n\n"
        "Hey there! Im M0THB0T"
        "Use /whatis to learn more about me!"
    )
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def whatis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_description = (
        "*M0THB0T*\n\n"
        "*Created by:* @MOTHHHHHHHHHH\n"
        "*Status:* 🚧 In Development\n\n"
        "*About:* M0THB0T is a custom Telegram bot designed to "
        "bring fun and useful features to your chats. Currently "
        "being developed with new features coming soon!\n\n"
        "*Version:* 1.1 Beta\n"
        "*Bot Type:* Utility & Fun\n\n"
        "Stay tuned for updates! 🍻🙀"
    )
    await update.message.reply_text(bot_description, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🦋 *M0THB0T Commands*\n\n"
        "/start - Wake up the bot\n"
        "/whatis - Learn about M0THB0T\n"
        "/help - Show this help message\n\n"
        "More commands coming soon!"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ===== MAIN FUNCTION =====
def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("Flask keep-alive server started on port 10000")
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("whatis", whatis))
    app.add_handler(CommandHandler("help", help_command))
    
    print("🦋 M0THB0T is starting...")
    print("Bot is now running 24/7!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)

if __name__ == "__main__":
    print("Initializing M0THB0T...")
    main()
