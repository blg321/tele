import telebot
import socket
import os
import hashlib
import hmac
import time
from ipaddress import ip_address
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ─────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
SHARED_SECRET = os.getenv("SHARED_SECRET")
ADMIN_ID_STR = os.getenv("ADMIN_ID", "")

AUTHORIZED_USERS = []
for uid in ADMIN_ID_STR.split(","):
    uid = uid.strip()
    if uid:
        AUTHORIZED_USERS.append(int(uid))

# Rate limiting
REQUEST_LOG = {}
MAX_REQUESTS = 5
RATE_WINDOW = 60

# Failed auth tracking
FAILED_ATTEMPTS = {}
MAX_FAILED = 5
LOCKOUT_MINUTES = 30

# GeoIP - pure local, zero network
GEO_READER = None
try:
    import geoip2.database
    GEO_READER = geoip2.database.Reader("./GeoLite2-City.mmdb")
    print("[✓] GeoIP database loaded (local, no external requests)")
except ImportError:
    print("[!] geoip2 not installed")
except FileNotFoundError:
    print("[!] GeoLite2-City.mmdb not found in project directory")
except Exception as e:
    print(f"[!] GeoIP init error: {e}")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ─── Security Checks ───────────────────────────

def is_authorized(user_id):
    return user_id in AUTHORIZED_USERS

def check_rate_limit(user_id):
    now = time.time()
    if user_id not in REQUEST_LOG:
        REQUEST_LOG[user_id] = []
    
    REQUEST_LOG[user_id] = [
        t for t in REQUEST_LOG[user_id]
        if now - t < RATE_WINDOW
    ]
    
    if len(REQUEST_LOG[user_id]) >= MAX_REQUESTS:
        return True
    
    REQUEST_LOG[user_id].append(now)
    return False

def is_locked_out(user_id):
    if user_id not in FAILED_ATTEMPTS:
        return False
    
    count, first_time = FAILED_ATTEMPTS[user_id]
    if count >= MAX_FAILED:
        if time.time() - first_time < LOCKOUT_MINUTES * 60:
            return True
        else:
            del FAILED_ATTEMPTS[user_id]
    return False

def record_failed_attempt(user_id):
    now = time.time()
    if user_id not in FAILED_ATTEMPTS:
        FAILED_ATTEMPTS[user_id] = (1, now)
    else:
        count, first_time = FAILED_ATTEMPTS[user_id]
        if now - first_time > LOCKOUT_MINUTES * 60:
            FAILED_ATTEMPTS[user_id] = (1, now)
        else:
            FAILED_ATTEMPTS[user_id] = (count + 1, first_time)

def verify_hmac(message_text, timestamp, received_hash):
    payload = f"{message_text}:{timestamp}".encode('utf-8')
    expected = hmac.new(
        SHARED_SECRET.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received_hash)

# ─── IP Functions (all local) ──────────────────

def validate_ip(ip):
    try:
        parsed = ip_address(ip.strip())
        return str(parsed)
    except ValueError:
        raise ValueError(f"Invalid IP: {ip}")

def is_private_ip(ip):
    try:
        return ip_address(ip).is_private
    except:
        return False

def get_geo(ip):
    if not GEO_READER:
        return {"error": "GeoIP database not loaded"}

    try:
        response = GEO_READER.city(ip)
        return {
            "city": response.city.name or "Unknown",
            "region": response.subdivisions.most_specific.name or "Unknown",
            "country": response.country.name or "Unknown",
            "continent": response.continent.name or "Unknown",
            "postal": response.postal.code or "Unknown",
            "lat": str(response.location.latitude) if response.location.latitude else "N/A",
            "lon": str(response.location.longitude) if response.location.longitude else "N/A",
            "timezone": response.location.time_zone or "Unknown"
        }
    except geoip2.errors.AddressNotFoundError:
        return {"error": "IP not found in database"}
    except Exception as e:
        return {"error": f"Lookup error: {e}"}

def get_rdns(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except socket.herror:
        return "No PTR record found"
    except Exception:
        return "DNS lookup failed"

# ─── Bot Commands ──────────────────────────────

@bot.message_handler(commands=['start'])
def start(message):
    if not is_authorized(message.from_user.id):
        return
    bot.reply_to(message, "Bot online. /lookup [ip] | /hmac [cmd] [ts] [hash] | /auth")

@bot.message_handler(commands=['lookup'])
def ip_lookup(message):
    user_id = message.from_user.id

    if not is_authorized(user_id):
        return

    if is_locked_out(user_id):
        bot.reply_to(message, "🔒 Locked out. Try again later.")
        return

    if check_rate_limit(user_id):
        bot.reply_to(message, "⏳ Rate limit reached. Wait 60s.")
        return

    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "<b>Usage:</b> <code>/lookup 8.8.8.8</code>")
        return

    ip = parts[1]

    try:
        ip = validate_ip(ip)
    except ValueError:
        bot.reply_to(message, "❌ Invalid IP address.")
        return

    private = is_private_ip(ip)
    geo_data = get_geo(ip)
    rdns = get_rdns(ip)

    lines = [f"<b>IP:</b> <code>{ip}</code>"]

    if private:
        lines.append("<b>Type:</b> 🔒 Private/Internal")

    if "error" not in geo_data:
        lines.extend([
            f"<b>City:</b> {geo_data['city']}",
            f"<b>Region:</b> {geo_data['region']}",
            f"<b>Country:</b> {geo_data['country']}",
            f"<b>Continent:</b> {geo_data['continent']}",
            f"<b>Postal:</b> {geo_data['postal']}",
            f"<b>Timezone:</b> {geo_data['timezone']}",
            f"<b>Coordinates:</b> {geo_data['lat']}, {geo_data['lon']}"
        ])
    else:
        lines.append(f"<b>Geo:</b> {geo_data['error']}")

    lines.append(f"<b>Reverse DNS:</b> {rdns}")

    bot.reply_to(message, "\n".join(lines))

@bot.message_handler(commands=['hmac'])
def hmac_command(message):
    user_id = message.from_user.id

    if not is_authorized(user_id):
        return

    if is_locked_out(user_id):
        bot.reply_to(message, "🔒 Locked out due to failed attempts.")
        return

    parts = message.text.split()
    if len(parts) != 4:
        record_failed_attempt(user_id)
        bot.reply_to(message, "❌ Invalid auth format.")
        return

    command = parts[1]
    timestamp = parts[2]
    provided_hmac = parts[3]

    try:
        ts = int(timestamp)
        now = int(time.time())
        if abs(now - ts) > 30:
            record_failed_attempt(user_id)
            bot.reply_to(message, "⏰ Request expired. Regenerate HMAC.")
            return
    except ValueError:
        record_failed_attempt(user_id)
        bot.reply_to(message, "❌ Invalid timestamp.")
        return

    if not verify_hmac(command, timestamp, provided_hmac):
        record_failed_attempt(user_id)
        bot.reply_to(message, "🔑 Authentication failed.")
        return

    bot.reply_to(
        message,
        f"✅ HMAC verified.\n"
        f"<b>Command:</b> <code>{command}</code>\n"
        f"<i>(Execution logic goes here)</i>"
    )

@bot.message_handler(commands=['auth'])
def auth_help(message):
    if not is_authorized(message.from_user.id):
        return

    help_text = """
<b>🔐 Generate HMAC locally:</b>

<b>Python:</b>
<code>import hmac, hashlib, time
secret = "YOUR_SECRET"
cmd = "status"
ts = str(int(time.time()))
h = hmac.new(secret.encode(), f"{cmd}:{ts}".encode(), hashlib.sha256).hexdigest()
print(f"/hmac {cmd} {ts} {h}")</code>

<b>Bash:</b>
<code>SECRET="YOUR_SECRET"
CMD="status"
TS=$(date +%s)
H=$(echo -n "$CMD:$TS" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)
echo "/hmac $CMD $TS $H"</code>
    """
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['health'])
def health_check(message):
    if not is_authorized(message.from_user.id):
        return
    status = "Loaded" if GEO_READER else "Missing"
    bot.reply_to(message, f"✅ Online | GeoIP: {status} | 0 external requests")

@bot.message_handler(func=lambda m: True)
def catch_all(message):
    if not is_authorized(message.from_user.id):
        return
    bot.reply_to(message, "Unknown command. /start for options.")

# ─── Startup ───────────────────────────────────

def validate_config():
    errors = []

    if not BOT_TOKEN:
        errors.append("BOT_TOKEN not set")
    if not SHARED_SECRET or len(SHARED_SECRET) < 32:
        errors.append("SHARED_SECRET must be at least 32 characters")
    if not AUTHORIZED_USERS:
        errors.append("ADMIN_ID not set")

    if errors:
        print("[!] Configuration errors:")
        for e in errors:
            print(f"    - {e}")
        return False

    print(f"[✓] Authorized users: {len(AUTHORIZED_USERS)}")
    print(f"[✓] GeoIP: {'Loaded' if GEO_READER else 'Missing (local only, no API calls)'}")
    print(f"[✓] Rate limit: {MAX_REQUESTS} req/{RATE_WINDOW}s")
    print(f"[✓] HMAC lockout: {MAX_FAILED} fails = {LOCKOUT_MINUTES}min")
    print("[✓] Network: ZERO external requests at runtime")
    return True

if __name__ == "__main__":
    if not validate_config():
        exit(1)

    print("[✓] Bot starting...")
    bot.infinity_polling(timeout=30, long_polling_timeout=30)
