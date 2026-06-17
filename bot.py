import os
import json
import asyncio
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ===== CONFIGURATION - READ FROM ENVIRONMENT =====
BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_BOT_TOKEN_HERE_IF_NO_ENV")

AUTHORIZED_USERS = {
    6539961810,     # Your ID
    8924961685,     # Added user
    7692122363,     # Added user
    # Add 3 test user IDs below when you have them
    # 987654321,
    # 555111222,
    # 444333555,
}
# =================================================

# Bot state file (for persistence across restarts)
STATE_FILE = "bot_state.json"

# Global variables
bot_mode = "normal"  # normal, silence, lockdown

# ========== HEALTH SERVER FOR RENDER (NO MORE PORT ISSUES) ==========
class HealthHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler that keeps Render happy"""
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running")
    
    def log_message(self, format, *args):
        # Suppress HTTP server logs (keeps console clean)
        pass

def run_health_server():
    """Run a minimal HTTP server on Render's expected port"""
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

# Start the health server in a background thread
health_thread = threading.Thread(target=run_health_server, daemon=True)
health_thread.start()
# ===================================================================

def load_state():
    """Load bot mode from file"""
    global bot_mode
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                bot_mode = data.get('mode', 'normal')
        except:
            bot_mode = 'normal'
    else:
        bot_mode = 'normal'

def save_state():
    """Save bot mode to file"""
    with open(STATE_FILE, 'w') as f:
        json.dump({'mode': bot_mode}, f)

def is_authorized(user_id):
    """Check if user is authorized"""
    return user_id in AUTHORIZED_USERS

async def check_permission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if user is authorized to use commands. Returns False if they should be ignored entirely."""
    user_id = update.effective_user.id
    
    # Lockdown mode: block EVERYONE (even authorized)
    if bot_mode == "lockdown":
        return False
    
    # Silence mode: only block unauthorized
    if bot_mode == "silence":
        if not is_authorized(user_id):
            return False
    
    # Normal mode or authorized user in silence mode
    if not is_authorized(user_id):
        return False
    
    return True

# ========== COMMAND HANDLERS ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple start command - only for authorized users"""
    if not await check_permission(update, context):
        return
    
    await update.message.reply_text(
        f"🤖 Bot is online.\n"
        f"Mode: {bot_mode}\n"
        f"Authorized users: {len(AUTHORIZED_USERS)}\n\n"
        f"Commands:\n"
        f"/silence - Block non-authorized users\n"
        f"/lockdown - Block everyone (including you)\n"
        f"/unlock or /speak - End lockdown/silence\n"
        f"/msg <user_id> <text> - DM any user\n"
        f"/broadcast <text> - DM all authorized users\n"
        f"/whisper - Alias for /msg"
    )

async def silence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Block non-authorized users"""
    if not await check_permission(update, context):
        return
    
    global bot_mode
    bot_mode = "silence"
    save_state()
    await update.message.reply_text("🔇 Silence mode activated. Non-authorized users will receive no responses.")

async def lockdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Block everyone including authorized users"""
    if not await check_permission(update, context):
        return
    
    global bot_mode
    bot_mode = "lockdown"
    save_state()
    await update.message.reply_text("🔒 LOCKDOWN activated. Even you will be ignored until /unlock. Bot will only respond to /unlock or /speak from authorized users.")

async def unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unlock the bot (end silence or lockdown)"""
    if not is_authorized(update.effective_user.id):
        return
    
    global bot_mode
    bot_mode = "normal"
    save_state()
    await update.message.reply_text("🔓 Bot unlocked. Normal operation restored.")

# /speak is an alias for /unlock
speak = unlock

async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """DM any Telegram user by their numeric ID"""
    if not await check_permission(update, context):
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: /msg <user_id> <message>\nExample: /msg 123456789 Hello there!")
        return
    
    try:
        target_user_id = int(context.args[0])
        message_text = ' '.join(context.args[1:])
        
        await context.bot.send_message(chat_id=target_user_id, text=message_text)
        await update.message.reply_text(f"✅ Message sent to user {target_user_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Must be a number.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send message: {str(e)}")

# /whisper is an alias for /msg
whisper = msg

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message to all authorized users"""
    if not await check_permission(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /broadcast <message>\nExample: /broadcast Server maintenance in 5 minutes")
        return
    
    message_text = ' '.join(context.args)
    sent_count = 0
    failed_count = 0
    
    for user_id in AUTHORIZED_USERS:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 BROADCAST:\n\n{message_text}")
            sent_count += 1
        except Exception as e:
            failed_count += 1
            print(f"Failed to send to {user_id}: {e}")
    
    await update.message.reply_text(f"✅ Broadcast sent to {sent_count} users. Failed: {failed_count}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current bot status"""
    if not await check_permission(update, context):
        return
    
    mode_emoji = {
        "normal": "🟢",
        "silence": "🟡",
        "lockdown": "🔴"
    }
    
    await update.message.reply_text(
        f"📊 Bot Status\n"
        f"Mode: {mode_emoji.get(bot_mode, '⚪')} {bot_mode.upper()}\n"
        f"Authorized users: {len(AUTHORIZED_USERS)}\n"
        f"Your ID: {update.effective_user.id}"
    )

async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Health check endpoint for cron-job.org"""
    # This can be accessed without auth for monitoring
    await update.message.reply_text(f"OK - {datetime.now().isoformat()}")

# ========== MAIN ==========

def main():
    # Validate token is set
    if BOT_TOKEN == "PUT_BOT_TOKEN_HERE_IF_NO_ENV":
        print("❌ ERROR: BOT_TOKEN environment variable not set!")
        print("Please set it in Render dashboard under Environment Variables")
        return
    
    # Load saved state
    load_state()
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("silence", silence))
    app.add_handler(CommandHandler("lockdown", lockdown))
    app.add_handler(CommandHandler("unlock", unlock))
    app.add_handler(CommandHandler("speak", speak))
    app.add_handler(CommandHandler("msg", msg))
    app.add_handler(CommandHandler("whisper", whisper))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("health", health))
    
    # Start bot
    print(f"🤖 Bot starting...")
    print(f"📊 Initial mode: {bot_mode}")
    print(f"👥 Authorized users: {len(AUTHORIZED_USERS)}")
    print(f"🌐 Health server running on port {os.environ.get('PORT', 10000)}")
    
    app.run_polling()

if __name__ == "__main__":
    main()
