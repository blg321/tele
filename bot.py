import os
import hashlib
import aiohttp
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
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

# ===== COMMAND HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "🦋 *M0THB0T is online!*\n\n"
        "Hey there! I'm your friendly neighborhood moth bot.\n"
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
        "*Bot Type:* Utility\n\n"
        "Stay tuned for updates! 🙀🍻"
    )
    await update.message.reply_text(bot_description, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "*M0THB0T Commands*\n\n"
        "/start - Wake up the bot\n"
        "/whatis - Learn about M0THB0T\n"
        "/help - Show this help message\n"
        "/define <word> - Get dictionary definition\n"
        "/pwnedpassword <password> - Check if password was in data breaches\n\n"
        "More commands coming soon!"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ===== NEW COMMAND: DICTIONARY DEFINITION =====
async def define(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "📚 *Usage:* `/define <word>`\n"
            "Example: `/define butterfly`",
            parse_mode='Markdown'
        )
        return
    
    word = ' '.join(context.args).lower()
    await update.message.reply_text(f"🔍 Looking up definition for *{word}*...", parse_mode='Markdown')
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
            async with session.get(url) as response:
                if response.status == 404:
                    await update.message.reply_text(
                        f"❌ Sorry, couldn't find definition for *{word}*. Please check the spelling.",
                        parse_mode='Markdown'
                    )
                    return
                
                if response.status != 200:
                    await update.message.reply_text(
                        "⚠️ Dictionary service is temporarily unavailable. Please try again later.",
                        parse_mode='Markdown'
                    )
                    return
                
                data = await response.json()
                
                if not data:
                    await update.message.reply_text(f"❌ No definition found for *{word}*.", parse_mode='Markdown')
                    return
                
                # Extract definition data
                word_info = data[0]
                word_name = word_info.get('word', word)
                phonetic = word_info.get('phonetic', 'No pronunciation available')
                
                meanings = word_info.get('meanings', [])
                
                result = f"📖 *Definition: {word_name.capitalize()}*\n"
                result += f"🔊 *Pronunciation:* {phonetic}\n\n"
                
                for i, meaning in enumerate(meanings[:2], 1):  # Limit to 2 meanings to avoid huge messages
                    part_of_speech = meaning.get('partOfSpeech', 'Unknown')
                    result += f"*{i}. {part_of_speech.capitalize()}:*\n"
                    
                    definitions = meaning.get('definitions', [])
                    for j, definition in enumerate(definitions[:2], 1):  # Limit to 2 definitions per meaning
                        def_text = definition.get('definition', 'No definition')
                        example = definition.get('example')
                        
                        result += f"   {j}. {def_text}\n"
                        if example:
                            result += f"      *Example:* \"{example}\"\n"
                    result += "\n"
                
                # Add note if there are more meanings
                if len(meanings) > 2 or any(len(m.get('definitions', [])) > 2 for m in meanings[:2]):
                    result += "_Note: Showing top definitions. Use a dictionary for complete results._"
                
                await update.message.reply_text(result, parse_mode='Markdown')
                
    except aiohttp.ClientError:
        await update.message.reply_text(
            "🌐 Network error. Please check your connection and try again.",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ An error occurred: {str(e)}",
            parse_mode='Markdown'
        )

# ===== NEW COMMAND: PWNED PASSWORD CHECKER =====
async def pwnedpassword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "🔐 *Usage:* `/pwnedpassword <password>`\n"
            "Example: `/pwnedpassword password123`\n\n"
            "*Note:* Your password is never sent in plain text!",
            parse_mode='Markdown'
        )
        return
    
    password = ' '.join(context.args)
    
    # Show that we're checking (but don't show the password)
    await update.message.reply_text("🔐 *Checking password...*", parse_mode='Markdown')
    
    try:
        # Hash the password with SHA-1
        sha1_hash = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
        prefix = sha1_hash[:5]  # First 5 characters (k-anonymity)
        suffix = sha1_hash[5:]  # Rest of the hash
        
        async with aiohttp.ClientSession() as session:
            url = f"https://api.pwnedpasswords.com/range/{prefix}"
            async with session.get(url) as response:
                if response.status != 200:
                    await update.message.reply_text(
                        "⚠️ Password checking service is temporarily unavailable. Please try again later.",
                        parse_mode='Markdown'
                    )
                    return
                
                hashes = await response.text()
                
                # Check if our suffix exists in the response
                found = False
                for line in hashes.splitlines():
                    if line.startswith(suffix):
                        count = line.split(':')[1]
                        found = True
                        await update.message.reply_text(
                            f"⚠️ *PASSWORD COMPROMISED!*\n\n"
                            f"This password has appeared in data breaches **{count} times**!\n\n"
                            f"*Recommendation:* Do NOT use this password. Generate a strong, unique password immediately.\n\n"
                            f"🔒 Tips for strong passwords:\n"
                            f"• Use 12+ characters\n"
                            f"• Mix uppercase, lowercase, numbers, and symbols\n"
                            f"• Never reuse passwords across sites\n"
                            f"• Use a password manager",
                            parse_mode='Markdown'
                        )
                        break
                
                if not found:
                    await update.message.reply_text(
                        f"✅ *PASSWORD SAFE!*\n\n"
                        f"Good news! This password hasn't appeared in any known data breaches.\n\n"
                        f"*Keep it secure:*\n"
                        f"• Never share it with anyone\n"
                        f"• Enable 2-factor authentication when available\n"
                        f"• Still avoid reusing it across multiple sites",
                        parse_mode='Markdown'
                    )
                
    except aiohttp.ClientError:
        await update.message.reply_text(
            "🌐 Network error. Please check your connection and try again.",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ An error occurred: {str(e)}",
            parse_mode='Markdown'
        )

# ===== MAIN FUNCTION =====
def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("Flask keep-alive server started on port 10000")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("whatis", whatis))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("define", define))
    app.add_handler(CommandHandler("pwnedpassword", pwnedpassword))
    
    print("🦋 M0THB0T is starting...")
    print("Bot is now running 24/7!")
    print("✅ Available commands: /start, /whatis, /help, /define, /pwnedpassword")
    app.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)

if __name__ == "__main__":
    print("Initializing M0THB0T...")
    main()
