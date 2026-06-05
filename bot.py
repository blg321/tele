import os
import asyncio
from flask import Flask
from threading import Thread
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

# ===== FLASK FOR KEEPING ALIVE =====
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "M0THB0T is alive and running!"

def run_flask():
    app_flask.run(host='0.0.0.0', port=10000)

# ===== BOT CONFIGURATION =====
# IMPORTANT: Use environment variable, never hardcode tokens!
BOT_TOKEN = os.environ.get('BOT_TOKEN')

if not BOT_TOKEN:
    print("WARNING: No BOT_TOKEN found!")
    print("Using fallback token - INSECURE FOR PRODUCTION!")
    BOT_TOKEN = "8933546826:AAEAKQ3JRicYgI0UCZ8YxvcR-7NKb12BYDE"  # Replace or better use environment variable

# ===== COMMAND HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when /start is issued."""
    welcome_message = (
        "🦋 *M0THB0T is online!*\n\n"
        "Hey there! I'm your friendly neighborhood moth bot.\n"
        "Use /whatis to learn more about me!"
    )
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def whatis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respond with bot description."""
    bot_description = (
        "🦋 *M0THB0T*\n\n"
        "*Created by:* @MOTHHHHHHHHHH\n"
        "*Status:* 🚧 In Development\n\n"
        "*About:* M0THB0T is a custom Telegram bot designed to "
        "bring fun and useful features to your chats. Currently "
        "being developed with new features coming soon!\n\n"
        "*Version:* 1.0 Beta\n"
        "*Bot Type:* Utility & Fun\n\n"
        "Stay tuned for updates! 🦋✨"
    )
    await update.message.reply_text(bot_description, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when /help is issued."""
    help_text = (
        "🦋 *M0THB0T Commands*\n\n"
        "/start - Wake up the bot\n"
        "/whatis - Learn about M0THB0T\n"
        "/help - Show this help message\n\n"
        "More commands coming soon!"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    print(f"Update {update} caused error {context.error}")

# ===== MAIN FUNCTION =====
async def main():
    """Start the bot."""
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("Flask keep-alive server started on port 10000")
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("whatis", whatis))
    app.add_handler(CommandHandler("help", help_command))
    
    # Add error handler
    app.add_error_handler(error_handler)
    
    # Start bot
    print("🦋 M0THB0T is starting...")
    print("Bot is now running 24/7!")
    
    # Run the bot
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    print("Initializing M0THB0T...")
    asyncio.run(main())
