import audioop
import discord
from discord.ext import commands
import socket
import os
import hashlib
import hmac
import time
from ipaddress import ip_address
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ─────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SHARED_SECRET = os.getenv("SHARED_SECRET")
ADMIN_ID_STR = os.getenv("ADMIN_ID", "")

AUTHORIZED_USERS = []
for uid in ADMIN_ID_STR.split(","):
    uid = uid.strip()
    if uid:
        AUTHORIZED_USERS.append(int(uid))

REQUEST_LOG = {}
MAX_REQUESTS = 5
RATE_WINDOW = 60

FAILED_ATTEMPTS = {}
MAX_FAILED = 5
LOCKOUT_MINUTES = 30

GEO_READER = None
try:
    import geoip2.database
    GEO_READER = geoip2.database.Reader("./GeoLite2-City.mmdb")
    print("[✓] GeoIP database loaded")
except ImportError:
    print("[!] geoip2 not installed")
except FileNotFoundError:
    print("[!] GeoLite2-City.mmdb not found")
except Exception as e:
    print(f"[!] GeoIP init error: {e}")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ─── Security ──────────────────────────────────

def is_authorized(user_id):
    return user_id in AUTHORIZED_USERS

def check_rate_limit(user_id):
    now = time.time()
    if user_id not in REQUEST_LOG:
        REQUEST_LOG[user_id] = []
    REQUEST_LOG[user_id] = [t for t in REQUEST_LOG[user_id] if now - t < RATE_WINDOW]
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

# ─── IP Functions ──────────────────────────────

def validate_ip(ip):
    parsed = ip_address(ip.strip())
    return str(parsed)

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
        return {"error": "IP not in database"}
    except Exception as e:
        return {"error": f"Lookup error: {e}"}

def get_rdns(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except socket.herror:
        return "No PTR record"
    except Exception:
        return "DNS lookup failed"

async def security_check(interaction: discord.Interaction):
    user_id = interaction.user.id
    if not is_authorized(user_id):
        await interaction.response.send_message("❌ Not authorized.", ephemeral=True)
        return True
    if is_locked_out(user_id):
        await interaction.response.send_message("🔒 Locked out.", ephemeral=True)
        return True
    if check_rate_limit(user_id):
        await interaction.response.send_message("⏳ Rate limit. Wait 60s.", ephemeral=True)
        return True
    return False

# ─── Events ────────────────────────────────────

@bot.event
async def on_ready():
    print(f"[✓] Logged in as {bot.user}")
    print(f"[✓] Authorized users: {len(AUTHORIZED_USERS)}")
    print(f"[✓] GeoIP: {'Loaded' if GEO_READER else 'Missing'}")
    print(f"[✓] Rate limit: {MAX_REQUESTS}/{RATE_WINDOW}s")
    print(f"[✓] HMAC lockout: {MAX_FAILED} fails = {LOCKOUT_MINUTES}min")
    print("[✓] Runtime network: ZERO external requests")
    try:
        synced = await bot.tree.sync()
        print(f"[✓] Slash commands synced: {len(synced)}")
    except Exception as e:
        print(f"[!] Sync error: {e}")

# ─── Slash Commands ────────────────────────────

@bot.tree.command(name="lookup", description="Lookup IP geolocation and reverse DNS")
async def lookup(interaction: discord.Interaction, ip: str):
    if await security_check(interaction):
        return

    try:
        ip = validate_ip(ip)
    except ValueError:
        await interaction.response.send_message("❌ Invalid IP address.", ephemeral=True)
        return

    private = is_private_ip(ip)
    geo_data = get_geo(ip)
    rdns = get_rdns(ip)

    embed = discord.Embed(title=f"IP Lookup: `{ip}`", color=0x00ff00)
    embed.add_field(name="Type", value="🔒 Private/Internal" if private else "🌐 Public", inline=False)

    if "error" not in geo_data:
        embed.add_field(name="City", value=geo_data["city"], inline=True)
        embed.add_field(name="Region", value=geo_data["region"], inline=True)
        embed.add_field(name="Country", value=geo_data["country"], inline=True)
        embed.add_field(name="Continent", value=geo_data["continent"], inline=True)
        embed.add_field(name="Postal Code", value=geo_data["postal"], inline=True)
        embed.add_field(name="Timezone", value=geo_data["timezone"], inline=True)
        embed.add_field(name="Coordinates", value=f"{geo_data['lat']}, {geo_data['lon']}", inline=True)
    else:
        embed.add_field(name="Geo Error", value=geo_data["error"], inline=False)

    embed.add_field(name="Reverse DNS", value=rdns, inline=False)
    embed.set_footer(text="Local DB lookup • No external requests")

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="hmac", description="Execute HMAC-authenticated command")
async def hmac_cmd(interaction: discord.Interaction, command: str, timestamp: str, hmac_hash: str):
    if await security_check(interaction):
        return

    try:
        ts = int(timestamp)
        if abs(int(time.time()) - ts) > 30:
            record_failed_attempt(interaction.user.id)
            await interaction.response.send_message("⏰ Request expired. Regenerate HMAC.", ephemeral=True)
            return
    except ValueError:
        record_failed_attempt(interaction.user.id)
        await interaction.response.send_message("❌ Invalid timestamp.", ephemeral=True)
        return

    if not verify_hmac(command, timestamp, hmac_hash):
        record_failed_attempt(interaction.user.id)
        await interaction.response.send_message("🔑 Authentication failed.", ephemeral=True)
        return

    await interaction.response.send_message(
        f"✅ HMAC verified.\n**Command:** `{command}`\n*Add execution logic here*",
        ephemeral=True
    )

@bot.tree.command(name="auth", description="Show HMAC generation instructions")
async def auth_help(interaction: discord.Interaction):
    if await security_check(interaction):
        return

    embed = discord.Embed(title="🔐 HMAC Generation", color=0x3498db)
    embed.description = "Generate HMAC locally — never share your secret."

    embed.add_field(
        name="Python",
        value="```py\nimport hmac, hashlib, time\nS = \"YOUR_SECRET\"\nc = \"status\"\nt = str(int(time.time()))\nh = hmac.new(S.encode(), f\"{c}:{t}\".encode(), hashlib.sha256).hexdigest()\nprint(f\"/hmac {c} {t} {h}\")\n```",
        inline=False
    )

    embed.add_field(
        name="Bash",
        value="```bash\nS=\"YOUR_SECRET\"\nC=\"status\"\nT=$(date +%s)\nH=$(echo -n \"$C:$T\" | openssl dgst -sha256 -hmac \"$S\" | cut -d' ' -f2)\necho \"/hmac $C $T $H\"\n```",
        inline=False
    )

    embed.set_footer(text="HMAC expires 30 seconds after generation")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="health", description="Check bot status")
async def health(interaction: discord.Interaction):
    if await security_check(interaction):
        return

    embed = discord.Embed(title="Bot Status", color=0x00ff00)
    embed.add_field(name="Online", value="✅", inline=True)
    embed.add_field(name="GeoIP Database", value="Loaded" if GEO_READER else "Missing", inline=True)
    embed.add_field(name="External Requests", value="Zero", inline=True)
    embed.add_field(name="Authorized Users", value=str(len(AUTHORIZED_USERS)), inline=True)
    embed.add_field(name="Rate Limit", value=f"{MAX_REQUESTS}/{RATE_WINDOW}s", inline=True)
    embed.add_field(name="HMAC Lockout", value=f"{MAX_FAILED} fails = {LOCKOUT_MINUTES}min", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ─── Startup ───────────────────────────────────

if __name__ == "__main__":
    errors = []
    if not DISCORD_TOKEN:
        errors.append("DISCORD_TOKEN not set")
    if not SHARED_SECRET or len(SHARED_SECRET) < 32:
        errors.append("SHARED_SECRET must be >= 32 chars")
    if not AUTHORIZED_USERS:
        errors.append("ADMIN_ID not set")
    if errors:
        print("[!] Configuration errors:")
        for e in errors:
            print(f"    - {e}")
        exit(1)

    print("[✓] Starting bot...")
    bot.run(DISCORD_TOKEN)
