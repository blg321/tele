import os
import re
import json
import base64
import hashlib
import string
import secrets
import socket
import ssl
import urllib.parse
import sys
from datetime import datetime
from collections import Counter
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

# Load environment
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
ALLOWED_USER_ID = os.getenv('ALLOWED_USER_ID')

# Validate environment variables
if not TOKEN:
    print("❌ ERROR: DISCORD_TOKEN not found in environment variables!")
    print("   Make sure you added it in Render's Environment tab")
    sys.exit(1)

if not ALLOWED_USER_ID:
    print("❌ ERROR: ALLOWED_USER_ID not found in environment variables!")
    print("   Make sure you added it in Render's Environment tab")
    sys.exit(1)

try:
    ALLOWED_USER_ID = int(ALLOWED_USER_ID)
except ValueError:
    print(f"❌ ERROR: ALLOWED_USER_ID must be a number, got: {ALLOWED_USER_ID}")
    sys.exit(1)

print(f"✅ Configuration loaded")
print(f"👤 Allowed User ID: {ALLOWED_USER_ID}")
print(f"🔑 Token found: {'Yes' if TOKEN else 'No'}")

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def is_allowed_user():
    """Restrict bot to single user"""
    async def predicate(ctx):
        if ctx.author.id != ALLOWED_USER_ID:
            await ctx.send("🔒 This bot is private. You're not authorized.", delete_after=5)
            return False
        return True
    return commands.check(predicate)

@bot.event
async def on_ready():
    print(f'🛡️ {bot.user.name} is online and secured!')
    print(f'👤 Authorized User ID: {ALLOWED_USER_ID}')
    print(f'🔗 Bot ID: {bot.user.id}')
    await bot.change_presence(activity=discord.Game(name="🛡️ Security Active"))

@bot.event
async def on_error(event, *args, **kwargs):
    """Global error handler"""
    print(f'❌ Error in {event}:', file=sys.stderr)
    import traceback
    traceback.print_exc()

# ============ PASSWORD & HASH TOOLS ============

@bot.command(name='hash')
@is_allowed_user()
async def hash_text(ctx, algorithm: str, *, text: str):
    """Generate various hashes: md5, sha1, sha256, sha512"""
    algorithms = {
        'md5': hashlib.md5,
        'sha1': hashlib.sha1,
        'sha256': hashlib.sha256,
        'sha512': hashlib.sha512
    }
    
    algo = algorithm.lower()
    if algo not in algorithms:
        await ctx.send(f"❌ Supported algorithms: {', '.join(algorithms.keys())}")
        return
    
    hash_obj = algorithms[algo](text.encode())
    hash_result = hash_obj.hexdigest()
    
    embed = discord.Embed(title=f"🔐 {algo.upper()} Hash", color=discord.Color.blue())
    embed.add_field(name="Input", value=f"```{text[:100]}```", inline=False)
    embed.add_field(name="Hash", value=f"```{hash_result}```", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='passgen')
@is_allowed_user()
async def password_generator(ctx, length: int = 16):
    """Generate strong random passwords"""
    if length < 8:
        await ctx.send("⚠️ Minimum password length is 8 characters")
        return
    if length > 128:
        await ctx.send("⚠️ Maximum password length is 128 characters")
        return
    
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    
    strength = "🟢 STRONG" if length >= 16 else "🟡 MEDIUM" if length >= 12 else "🔴 WEAK"
    
    embed = discord.Embed(title="🔑 Password Generated", color=discord.Color.green())
    embed.add_field(name="Password", value=f"```{password}```", inline=False)
    embed.add_field(name="Length", value=str(length), inline=True)
    embed.add_field(name="Strength", value=strength, inline=True)
    embed.set_footer(text="⚠️ This message will be deleted in 30 seconds")
    
    msg = await ctx.send(embed=embed)
    await asyncio.sleep(30)
    try:
        await msg.delete()
    except:
        pass

@bot.command(name='passcheck')
@is_allowed_user()
async def password_check(ctx, *, password: str):
    """Check password strength"""
    score = 0
    feedback = []
    
    if len(password) >= 16:
        score += 3
        feedback.append("✅ Excellent length (16+)")
    elif len(password) >= 12:
        score += 2
        feedback.append("✅ Good length (12+)")
    elif len(password) >= 8:
        score += 1
        feedback.append("⚠️ Minimum length (8+)")
    else:
        feedback.append("❌ Too short (less than 8)")
    
    if re.search(r'[A-Z]', password):
        score += 1
        feedback.append("✅ Has uppercase")
    else:
        feedback.append("❌ Missing uppercase")
    
    if re.search(r'[a-z]', password):
        score += 1
        feedback.append("✅ Has lowercase")
    else:
        feedback.append("❌ Missing lowercase")
    
    if re.search(r'\d', password):
        score += 1
        feedback.append("✅ Has numbers")
    else:
        feedback.append("❌ Missing numbers")
    
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 1
        feedback.append("✅ Has special characters")
    else:
        feedback.append("❌ Missing special characters")
    
    common_patterns = ['123', 'abc', 'qwerty', 'password', 'admin', 'letmein']
    if any(pattern in password.lower() for pattern in common_patterns):
        score -= 2
        feedback.append("❌ Contains common pattern")
    
    if score >= 7:
        strength = "🟢 VERY STRONG"
        color = discord.Color.green()
    elif score >= 5:
        strength = "🟡 STRONG"
        color = discord.Color.blue()
    elif score >= 3:
        strength = "🟠 MODERATE"
        color = discord.Color.orange()
    else:
        strength = "🔴 WEAK"
        color = discord.Color.red()
    
    embed = discord.Embed(title="🔍 Password Strength Analysis", color=color)
    embed.add_field(name="Strength", value=strength, inline=False)
    embed.add_field(name="Score", value=f"{score}/8", inline=True)
    embed.add_field(name="Length", value=str(len(password)), inline=True)
    embed.add_field(name="Feedback", value="\n".join(feedback), inline=False)
    embed.set_footer(text="Password not stored or logged")
    
    await ctx.send(embed=embed)

# ============ ENCODING/DECODING ============

@bot.command(name='b64e')
@is_allowed_user()
async def base64_encode(ctx, *, text: str):
    """Base64 encode text"""
    encoded = base64.b64encode(text.encode()).decode()
    embed = discord.Embed(title="📝 Base64 Encoded", color=discord.Color.blue())
    embed.add_field(name="Result", value=f"```{encoded[:1000]}```", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='b64d')
@is_allowed_user()
async def base64_decode(ctx, *, encoded_text: str):
    """Base64 decode text"""
    try:
        decoded = base64.b64decode(encoded_text.encode()).decode()
        embed = discord.Embed(title="📝 Base64 Decoded", color=discord.Color.green())
        embed.add_field(name="Result", value=f"```{decoded[:1000]}```", inline=False)
        await ctx.send(embed=embed)
    except:
        await ctx.send("❌ Invalid Base64 string")

@bot.command(name='urle')
@is_allowed_user()
async def url_encode(ctx, *, text: str):
    """URL encode text"""
    encoded = urllib.parse.quote(text)
    embed = discord.Embed(title="🔗 URL Encoded", color=discord.Color.blue())
    embed.add_field(name="Result", value=f"```{encoded[:1000]}```", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='urld')
@is_allowed_user()
async def url_decode(ctx, *, encoded_text: str):
    """URL decode text"""
    decoded = urllib.parse.unquote(encoded_text)
    embed = discord.Embed(title="🔗 URL Decoded", color=discord.Color.green())
    embed.add_field(name="Result", value=f"```{decoded[:1000]}```", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='hexe')
@is_allowed_user()
async def hex_encode(ctx, *, text: str):
    """Convert text to hex"""
    hex_str = text.encode().hex()
    embed = discord.Embed(title="🔢 Hex Encoded", color=discord.Color.blue())
    embed.add_field(name="Result", value=f"```{hex_str[:1000]}```", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='hexd')
@is_allowed_user()
async def hex_decode(ctx, *, hex_str: str):
    """Convert hex to text"""
    try:
        text = bytes.fromhex(hex_str).decode()
        embed = discord.Embed(title="🔢 Hex Decoded", color=discord.Color.green())
        embed.add_field(name="Result", value=f"```{text[:1000]}```", inline=False)
        await ctx.send(embed=embed)
    except:
        await ctx.send("❌ Invalid hex string")

# ============ NETWORK TOOLS ============

@bot.command(name='resolve')
@is_allowed_user()
async def dns_resolve(ctx, hostname: str):
    """Resolve hostname to IP"""
    try:
        ip = socket.gethostbyname(hostname)
        embed = discord.Embed(title=f"🌐 DNS Resolution: {hostname}", color=discord.Color.blue())
        embed.add_field(name="IP Address", value=ip, inline=True)
        embed.add_field(name="Hostname", value=hostname, inline=True)
        await ctx.send(embed=embed)
    except socket.gaierror:
        await ctx.send(f"❌ Could not resolve {hostname}")

@bot.command(name='reverse')
@is_allowed_user()
async def reverse_dns(ctx, ip: str):
    """Reverse DNS lookup"""
    try:
        hostname = socket.gethostbyaddr(ip)[0]
        embed = discord.Embed(title=f"🔄 Reverse DNS: {ip}", color=discord.Color.blue())
        embed.add_field(name="Hostname", value=hostname, inline=True)
        embed.add_field(name="IP", value=ip, inline=True)
        await ctx.send(embed=embed)
    except:
        await ctx.send(f"❌ No PTR record found for {ip}")

@bot.command(name='portscan')
@is_allowed_user()
async def quick_portscan(ctx, target: str, ports: str = "80,443,22,21,25,3306,8080"):
    """Quick scan common ports"""
    port_list = [int(p.strip()) for p in ports.split(',')]
    
    embed = discord.Embed(
        title=f"🔍 Quick Port Scan: {target}",
        description="Scanning...",
        color=discord.Color.orange()
    )
    msg = await ctx.send(embed=embed)
    
    results = []
    for port in port_list:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((target, port))
            if result == 0:
                try:
                    service = socket.getservbyport(port)
                except:
                    service = "unknown"
                results.append(f"✅ Port {port} ({service}) - OPEN")
            else:
                results.append(f"❌ Port {port} - CLOSED")
            sock.close()
        except Exception as e:
            results.append(f"⚠️ Port {port} - ERROR: {str(e)[:50]}")
    
    embed.description = "\n".join(results)
    embed.set_footer(text="⚠️ Only scan systems you own or have permission to test")
    await msg.edit(embed=embed)

@bot.command(name='sslinfo')
@is_allowed_user()
async def ssl_info(ctx, hostname: str, port: int = 443):
    """Get SSL certificate info"""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                
                embed = discord.Embed(
                    title=f"🔒 SSL Certificate: {hostname}:{port}",
                    color=discord.Color.green()
                )
                
                subject = dict(x[0] for x in cert['subject'])
                issuer = dict(x[0] for x in cert['issuer'])
                
                embed.add_field(name="Common Name", value=subject.get('commonName', 'N/A'), inline=True)
                embed.add_field(name="Organization", value=subject.get('organizationName', 'N/A'), inline=True)
                embed.add_field(name="Issuer", value=issuer.get('commonName', 'N/A'), inline=True)
                
                not_before = datetime.strptime(cert['notBefore'], '%b %d %H:%M:%S %Y %Z')
                not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                
                embed.add_field(name="Valid From", value=not_before.strftime('%Y-%m-%d'), inline=True)
                embed.add_field(name="Valid Until", value=not_after.strftime('%Y-%m-%d'), inline=True)
                
                days_left = (not_after - datetime.utcnow()).days
                if days_left > 0:
                    embed.add_field(name="Days Remaining", value=f"{days_left} days", inline=True)
                else:
                    embed.add_field(name="⚠️ Status", value="EXPIRED!", inline=True)
                
                await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ SSL check failed: {str(e)[:200]}")

# ============ TEXT ANALYSIS ============

@bot.command(name='analyze')
@is_allowed_user()
async def text_analyze(ctx, *, text: str):
    """Analyze text for patterns and statistics"""
    
    char_count = len(text)
    word_count = len(text.split())
    
    uppercase = sum(1 for c in text if c.isupper())
    lowercase = sum(1 for c in text if c.islower())
    digits = sum(1 for c in text if c.isdigit())
    special = sum(1 for c in text if not c.isalnum() and not c.isspace())
    
    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
    has_url = bool(re.search(r'https?://[^\s]+', text))
    has_ip = bool(re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text))
    has_phone = bool(re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', text))
    
    char_freq = Counter(c.lower() for c in text if c.isalpha())
    most_common = char_freq.most_common(5)
    
    embed = discord.Embed(title="📊 Text Analysis", color=discord.Color.purple())
    embed.add_field(name="Characters", value=str(char_count), inline=True)
    embed.add_field(name="Words", value=str(word_count), inline=True)
    embed.add_field(name="Lines", value=str(text.count('\n') + 1), inline=True)
    
    embed.add_field(name="Uppercase", value=str(uppercase), inline=True)
    embed.add_field(name="Lowercase", value=str(lowercase), inline=True)
    embed.add_field(name="Digits", value=str(digits), inline=True)
    embed.add_field(name="Special Chars", value=str(special), inline=True)
    
    patterns = []
    if has_email: patterns.append("📧 Email")
    if has_url: patterns.append("🔗 URL")
    if has_ip: patterns.append("🌐 IP Address")
    if has_phone: patterns.append("📱 Phone Number")
    
    if patterns:
        embed.add_field(name="Detected Patterns", value="\n".join(patterns), inline=False)
    
    if most_common:
        freq_str = "\n".join(f"'{char}': {count}x" for char, count in most_common)
        embed.add_field(name="Most Common Letters", value=f"```{freq_str}```", inline=False)
    
    if char_count > 0:
        unique_chars = len(set(text))
        entropy_ratio = unique_chars / char_count * 100
        embed.add_field(name="Unique Characters", value=f"{unique_chars} ({entropy_ratio:.1f}%)", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='regex')
@is_allowed_user()
async def regex_test(ctx, pattern: str, *, text: str):
    """Test regex patterns against text"""
    try:
        matches = re.findall(pattern, text)
        if matches:
            embed = discord.Embed(title="✅ Regex Matches Found", color=discord.Color.green())
            embed.add_field(name="Pattern", value=f"`{pattern}`", inline=False)
            embed.add_field(name="Matches", value=f"```{chr(10).join(str(m)[:100] for m in matches[:20])}```", inline=False)
            embed.add_field(name="Count", value=str(len(matches)), inline=True)
        else:
            embed = discord.Embed(title="❌ No Matches", color=discord.Color.red())
            embed.add_field(name="Pattern", value=f"`{pattern}`", inline=False)
        await ctx.send(embed=embed)
    except re.error as e:
        await ctx.send(f"❌ Invalid regex pattern: {str(e)}")

@bot.command(name='idgen')
@is_allowed_user()
async def id_generator(ctx, id_type: str = "uuid"):
    """Generate unique IDs (uuid, nano, custom)"""
    
    embed = discord.Embed(title="🆔 ID Generated", color=discord.Color.blue())
    
    if id_type.lower() == "uuid":
        import uuid
        uid = str(uuid.uuid4())
        embed.add_field(name="UUID v4", value=f"```{uid}```", inline=False)
    
    elif id_type.lower() == "nano":
        alphabet = string.ascii_letters + string.digits
        nano = ''.join(secrets.choice(alphabet) for _ in range(21))
        embed.add_field(name="Nano ID (21 chars)", value=f"```{nano}```", inline=False)
    
    else:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_part = ''.join(secrets.choice(string.hexdigits.lower()) for _ in range(8))
        custom_id = f"{timestamp}-{random_part}"
        embed.add_field(name="Custom ID", value=f"```{custom_id}```", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='tokeninfo')
@is_allowed_user()
async def token_analyze(ctx, token: str):
    """Analyze a potential JWT token"""
    parts = token.split('.')
    
    embed = discord.Embed(title="🔍 Token Analysis", color=discord.Color.orange())
    
    if len(parts) == 3:
        embed.add_field(name="Type", value="Likely JWT Token", inline=False)
        
        try:
            header = base64.urlsafe_b64decode(parts[0] + '==').decode()
            header_json = json.loads(header)
            embed.add_field(name="Header", value=f"```json\n{json.dumps(header_json, indent=2)[:500]}```", inline=False)
        except:
            embed.add_field(name="Header", value="Could not decode", inline=False)
        
        try:
            payload = base64.urlsafe_b64decode(parts[1] + '==').decode()
            payload_json = json.loads(payload)
            
            if 'exp' in payload_json:
                exp_time = datetime.fromtimestamp(payload_json['exp'])
                embed.add_field(name="Expires", value=exp_time.strftime('%Y-%m-%d %H:%M:%S UTC'), inline=True)
                if exp_time < datetime.utcnow():
                    embed.add_field(name="⚠️ Status", value="EXPIRED", inline=True)
            
            embed.add_field(name="Payload", value=f"```json\n{json.dumps(payload_json, indent=2)[:500]}```", inline=False)
        except:
            embed.add_field(name="Payload", value="Could not decode", inline=False)
    
    else:
        embed.add_field(name="Format", value="Not a standard JWT token", inline=False)
        try:
            decoded = base64.b64decode(token).decode()
            embed.add_field(name="Decoded", value=f"```{decoded[:200]}```", inline=False)
        except:
            embed.add_field(name="Note", value="Not a recognized token format", inline=False)
    
    embed.set_footer(text="⚠️ Never share real tokens! This is for educational analysis only.")
    await ctx.send(embed=embed)

@bot.command(name='security')
@is_allowed_user()
async def security_menu(ctx):
    """Display all security commands"""
    embed = discord.Embed(
        title="🛡️ Security Bot Commands",
        description="All tools run locally - no external APIs needed!",
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name="🔐 Password & Hash Tools",
        value="""
        `!hash <md5/sha1/sha256/sha512> <text>` - Hash text
        `!passgen <length>` - Generate strong password
        `!passcheck <password>` - Check password strength
        """,
        inline=False
    )
    
    embed.add_field(
        name="📝 Encoding/Decoding",
        value="""
        `!b64e <text>` - Base64 encode
        `!b64d <text>` - Base64 decode
        `!urle <text>` - URL encode
        `!urld <text>` - URL decode
        `!hexe <text>` - Hex encode
        `!hexd <text>` - Hex decode
        """,
        inline=False
    )
    
    embed.add_field(
        name="🌐 Network Tools",
        value="""
        `!resolve <hostname>` - DNS lookup
        `!reverse <ip>` - Reverse DNS
        `!portscan <host> [ports]` - Quick port scan
        `!sslinfo <host> [port]` - SSL certificate info
        """,
        inline=False
    )
    
    embed.add_field(
        name="🔍 Analysis & Utilities",
        value="""
        `!analyze <text>` - Text pattern analysis
        `!regex <pattern> <text>` - Test regex patterns
        `!idgen [uuid/nano/custom]` - Generate IDs
        `!tokeninfo <token>` - Analyze token structure
        """,
        inline=False
    )
    
    embed.set_footer(text="⚠️ Use responsibly and only on systems you own!")
    
    await ctx.send(embed=embed)

# Run bot with error handling
if __name__ == "__main__":
    print("🚀 Starting Discord Security Bot...")
    print("=" * 50)
    try:
        bot.run(TOKEN, log_handler=None)  # Disable default logging to avoid port binding issues
    except discord.LoginFailure:
        print("❌ Invalid Discord token! Check your DISCORD_TOKEN in environment variables.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        sys.exit(1)
