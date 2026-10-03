import asyncio
import json
import os
import platform
import random
import re
import socket
import sqlite3
import string
import subprocess
import time
from datetime import datetime, timedelta

import psutil
import pytz
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ButtonStyle
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    Message, BotCommand
)
from telethon import TelegramClient, events
from telethon.errors import (FloodWaitError, PhoneCodeExpiredError,
                             PhoneCodeInvalidError, PhoneNumberInvalidError,
                             SessionPasswordNeededError)
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.contacts import BlockRequest
from telethon.tl.types import KeyboardButtonCallback

# ==================== تنظیمات ====================
TOKEN = os.environ.get("TOKEN", "8961040480:AAGM9bGnba6JLjaXiaC5RjI-UNz-buzU4V8")
CHANNEL_USERNAME = "@ReaperSelfChannel"
ADMIN_IDS = [7803165903, 8831703400]

DB_FILE = "bot_database.db"

# ============ ایموجی‌های سفارشی (اختیاری) ============
# اگر می‌خواهید از ایموجی‌های پرمیوم استفاده کنید، ID آن‌ها را اینجا بگذارید.
# در غیر این صورت None بمانند و از ایموجی‌های یونیکد معمولی استفاده می‌شود.
EMOJI = {
    "panel": None,       # پنل
    "settings": None,    # تنظیمات
    "stats": None,       # آمار
    "ping": None,        # پینگ
    "host": None,        # هاست
    "users": None,       # کاربران
    "check": None,       # تیک
    "cross": None,       # ضربدر
    "clock": None,       # ساعت
    "read": None,        # خودخوان
    "reply": None,       # پاسخ
    "shield": None,      # ضد توهین
    "bio": None,         # بیو
    "name": None,        # اسم
    "chart": None,       # آنالیتیک
    "info": None,        # درباره
    "title": None,       # عنوان
    "lock": None,        # آنتی لاگین
    "auto": None,        # خودکار
    "banner": None,      # بنر
    "comment": None,     # کامنت
    "birthday": None,    # تولد
    "alert": None,       # هشدار
    "refresh": None,     # بروزرسانی
    "close": None,       # بستن
    "back": None,        # بازگشت
    "support": None,     # پشتیبانی
    "buy": None,         # خرید
    "key": None,         # کلید
    "rate": None,        # نرخ
    "verify": None,      # احراز
}

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            joined_date TEXT,
            is_banned INTEGER DEFAULT 0,
            is_verified INTEGER DEFAULT 0,
            remaining_days INTEGER DEFAULT 0,
            expiry_date TEXT,
            clock_active INTEGER DEFAULT 1
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS codes (
            code TEXT PRIMARY KEY,
            days INTEGER,
            expiry_date TEXT,
            created_date TEXT,
            used INTEGER DEFAULT 0,
            used_by TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER PRIMARY KEY,
            session_string TEXT,
            phone TEXT,
            api_hash TEXT,
            api_id INTEGER,
            created_date TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verify_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, username TEXT, card_number TEXT,
            photo_id TEXT, status TEXT DEFAULT 'pending',
            request_date TEXT, admin_response TEXT, response_date TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY, banned_date TEXT, reason TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, username TEXT, message TEXT,
            status TEXT DEFAULT 'open', created_date TEXT,
            admin_response TEXT, response_date TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS self_settings (
            user_id INTEGER PRIMARY KEY,
            clock_enabled INTEGER DEFAULT 0,
            auto_read INTEGER DEFAULT 0,
            auto_reply INTEGER DEFAULT 0,
            anti_insult INTEGER DEFAULT 0,
            animated_msg INTEGER DEFAULT 0,
            smart_secretary INTEGER DEFAULT 0,
            bio INTEGER DEFAULT 0,
            name_setting INTEGER DEFAULT 0,
            analytics INTEGER DEFAULT 0,
            about INTEGER DEFAULT 0,
            title INTEGER DEFAULT 0,
            anti_login INTEGER DEFAULT 0,
            auto_setting INTEGER DEFAULT 0,
            banner INTEGER DEFAULT 0,
            comment INTEGER DEFAULT 0,
            birthday INTEGER DEFAULT 0,
            alert INTEGER DEFAULT 0,
            classic INTEGER DEFAULT 1,
            modern INTEGER DEFAULT 0,
            persian INTEGER DEFAULT 1,
            english INTEGER DEFAULT 0,
            region INTEGER DEFAULT 1,
            public_self INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==================== STATE ====================
user_states = {}
salf_login_data = {}
clock_tasks = {}
admin_salf_data = {}
support_mode = {}
pending_verify = {}
user_menu_mode = {}
clock_status = {}
salf_clients = {}
self_tasks = {}

if not os.path.exists("sessions"):
    os.makedirs("sessions")

# ==================== DB FUNCTIONS ====================
def db_add_user(user_id, username, first_name, last_name, phone=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO users
        (user_id, username, first_name, last_name, phone, joined_date)
        VALUES (?, ?, ?, ?, ?, ?)''',
        (user_id, username, first_name, last_name, phone, datetime.now().isoformat()))
    conn.commit(); conn.close()

def db_is_banned(user_id):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
    r = c.fetchone(); conn.close()
    return r and r[0] == 1

def db_ban_user(user_id):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
    conn.commit(); conn.close()

def db_unban_user(user_id):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,))
    conn.commit(); conn.close()

def db_is_verified(user_id):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT is_verified FROM users WHERE user_id = ?', (user_id,))
    r = c.fetchone(); conn.close()
    return r and r[0] == 1

def db_verify_user(user_id):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('UPDATE users SET is_verified = 1 WHERE user_id = ?', (user_id,))
    conn.commit(); conn.close()

def db_add_code(code, days, expiry_date):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('INSERT INTO codes (code, days, expiry_date, created_date) VALUES (?, ?, ?, ?)',
              (code, days, expiry_date.isoformat(), datetime.now().isoformat()))
    conn.commit(); conn.close()

def db_get_code(code):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT * FROM codes WHERE code = ?', (code,))
    r = c.fetchone(); conn.close(); return r

def db_use_code(code, user_id):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('UPDATE codes SET used = 1, used_by = ? WHERE code = ?', (str(user_id), code))
    conn.commit(); conn.close()

def db_delete_code(code):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('DELETE FROM codes WHERE code = ?', (code,))
    conn.commit(); conn.close()

def db_save_session(user_id, session_string, phone, api_hash, api_id):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO sessions
        (user_id, session_string, phone, api_hash, api_id, created_date)
        VALUES (?, ?, ?, ?, ?, ?)''',
        (user_id, session_string, phone, api_hash, api_id, datetime.now().isoformat()))
    conn.commit(); conn.close()

def db_get_session(user_id):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT * FROM sessions WHERE user_id = ?', (user_id,))
    r = c.fetchone(); conn.close(); return r

def db_delete_session(user_id):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
    conn.commit(); conn.close()

def db_get_all_sessions():
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT * FROM sessions'); r = c.fetchall()
    conn.close(); return r

def db_get_self_settings(user_id):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT * FROM self_settings WHERE user_id = ?', (user_id,))
    r = c.fetchone(); conn.close()
    if r:
        keys = ['clock_enabled','auto_read','auto_reply','anti_insult','animated_msg',
                'smart_secretary','bio','name_setting','analytics','about','title',
                'anti_login','auto_setting','banner','comment','birthday','alert',
                'classic','modern','persian','english','region','public_self']
        return {k: bool(r[i+1]) for i, k in enumerate(keys)}
    return {
        'clock_enabled': False, 'auto_read': False, 'auto_reply': False,
        'anti_insult': False, 'animated_msg': False, 'smart_secretary': False,
        'bio': False, 'name_setting': False, 'analytics': False, 'about': False,
        'title': False, 'anti_login': False, 'auto_setting': False, 'banner': False,
        'comment': False, 'birthday': False, 'alert': False, 'classic': True,
        'modern': False, 'persian': True, 'english': False, 'region': True,
        'public_self': False
    }

def db_update_self_settings(user_id, s):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO self_settings
        (user_id, clock_enabled, auto_read, auto_reply, anti_insult, animated_msg,
         smart_secretary, bio, name_setting, analytics, about, title, anti_login,
         auto_setting, banner, comment, birthday, alert, classic, modern, persian,
         english, region, public_self)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (user_id, *[1 if s.get(k, False) else 0 for k in
         ['clock_enabled','auto_read','auto_reply','anti_insult','animated_msg',
          'smart_secretary','bio','name_setting','analytics','about','title',
          'anti_login','auto_setting','banner','comment','birthday','alert',
          'classic','modern','persian','english','region','public_self']]))
    conn.commit(); conn.close()

# ==================== HELPERS ====================
def is_admin(user_id): return user_id in ADMIN_IDS

def get_remaining_days(user_id):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT remaining_days FROM users WHERE user_id = ?', (user_id,))
    r = c.fetchone(); conn.close()
    return r[0] if r and r[0] else 0

def get_expiry_date(user_id):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT expiry_date FROM users WHERE user_id = ?', (user_id,))
    r = c.fetchone(); conn.close()
    if r and r[0]: return r[0].split('T')[0]
    return "ندارد"

def has_active_subscription(user_id): return get_remaining_days(user_id) > 0

def get_clock_status(user_id):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT clock_active FROM users WHERE user_id = ?', (user_id,))
    r = c.fetchone(); conn.close()
    return r[0] == 1 if r else True

def set_clock_status(user_id, status):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('UPDATE users SET clock_active = ? WHERE user_id = ?',
              (1 if status else 0, user_id))
    conn.commit(); conn.close()

def is_user_banned(user_id): return db_is_banned(user_id)
def ban_user(user_id): db_ban_user(user_id)
def unban_user(user_id): db_unban_user(user_id)
def is_user_verified(user_id): return db_is_verified(user_id)
def verify_user(user_id): db_verify_user(user_id)

def get_user_session(user_id):
    r = db_get_session(user_id)
    if r:
        return {'user_id': r[0], 'session': r[1], 'phone': r[2],
                'api_hash': r[3], 'api_id': r[4], 'created': r[5]}
    return None

def delete_user_session(user_id): db_delete_session(user_id)

def generate_code():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=15))

def create_new_code(days):
    while True:
        new_code = generate_code()
        if not db_get_code(new_code): break
    expiry = datetime.now() + timedelta(days=days)
    db_add_code(new_code, days, expiry)
    return new_code, expiry

def validate_code(code):
    r = db_get_code(code)
    if not r: return None, "❌ کد وارد شده صحیح نیست!"
    if r[4] == 1: return None, "❌ این کد قبلاً استفاده شده است!"
    if datetime.now() > datetime.fromisoformat(r[2]):
        return None, "⏳ کد وارد شده منقضی شده است!"
    return {'days': r[1], 'expiry': r[2]}, None

def use_code(code, user_id):
    r = db_get_code(code)
    if not r or r[4] == 1: return False
    db_use_code(code, user_id)
    days = r[1]
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT remaining_days FROM users WHERE user_id = ?', (user_id,))
    u = c.fetchone()
    if u:
        new_days = (u[0] or 0) + days
        expiry = datetime.now() + timedelta(days=new_days)
        c.execute('UPDATE users SET remaining_days = ?, expiry_date = ? WHERE user_id = ?',
                  (new_days, expiry.isoformat(), user_id))
    else:
        expiry = datetime.now() + timedelta(days=days)
        c.execute('INSERT INTO users (user_id, remaining_days, expiry_date) VALUES (?, ?, ?)',
                  (user_id, days, expiry.isoformat()))
    conn.commit(); conn.close(); return True

# ==================== دکمه ساز کمکی ====================
def make_btn(text, cb, style=None, emoji_id=None):
    """ساخت دکمه با استایل و ایموجی سفارشی (اگر پشتیبانی شود)"""
    kwargs = {"text": text, "callback_data": cb}
    if style:
        kwargs["style"] = style
    if emoji_id:
        kwargs["icon_custom_emoji_id"] = emoji_id
    try:
        return InlineKeyboardButton(**kwargs)
    except TypeError:
        # اگر نسخه aiogram پشتیبانی نکرد، بدون style/emoji بساز
        return InlineKeyboardButton(text=text, callback_data=cb)

# ==================== پنل سلف ====================
def build_panel_text(s):
    t = "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
    t += "   ⬢ **پنل مدیریت ریپر سلف** ⬢\n"
    t += "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
    t += "**⌬ لطفاً یکی از گزینه‌های زیر را انتخاب کنید:**\n\n"

    t += "◆━━━ 🎨 ظاهری ━━━◆\n"
    t += f"  {'✅' if s.get('classic', True) else '❌'} ◂ کلاسیک\n"
    t += f"  {'✅' if s.get('modern', False) else '❌'} ◂ مدرن\n"
    t += f"  {'✅' if s.get('persian', True) else '❌'} ◂ فارسی\n"
    t += f"  {'✅' if s.get('english', False) else '❌'} ◂ انگلیسی\n"
    t += f"  {'✅' if s.get('region', True) else '❌'} ◂ منطقه\n"
    t += f"  {'✅' if s.get('public_self', False) else '❌'} ◂ سلف همگانی\n"

    t += "\n◆━━━ 📋 اطلاعات ━━━◆\n"
    t += f"  {'✅' if s.get('bio', False) else '❌'} ◂ بیوگرافی\n"
    t += f"  {'✅' if s.get('name_setting', False) else '❌'} ◂ اسم\n"
    t += f"  {'✅' if s.get('analytics', False) else '❌'} ◂ آنالیتیک\n"
    t += f"  {'✅' if s.get('about', False) else '❌'} ◂ درباره\n"
    t += f"  {'✅' if s.get('title', False) else '❌'} ◂ عنوان\n"
    t += f"  {'✅' if s.get('anti_login', False) else '❌'} ◂ آنتی لاگین\n"

    t += "\n◆━━━ ⚡ قابلیت‌ها ━━━◆\n"
    t += f"  {'✅' if s.get('clock_enabled', False) else '❌'} ◂ ساعت\n"
    t += f"  {'✅' if s.get('auto_read', False) else '❌'} ◂ خودخوان\n"
    t += f"  {'✅' if s.get('auto_reply', False) else '❌'} ◂ پاسخ خودکار\n"
    t += f"  {'✅' if s.get('anti_insult', False) else '❌'} ◂ ضد توهین\n"
    t += f"  {'✅' if s.get('animated_msg', False) else '❌'} ◂ پیام انیمیشنی\n"
    t += f"  {'✅' if s.get('smart_secretary', False) else '❌'} ◂ منشی هوشمند\n"
    t += f"  {'✅' if s.get('auto_setting', False) else '❌'} ◂ خودکار\n"
    t += f"  {'✅' if s.get('banner', False) else '❌'} ◂ بنر\n"
    t += f"  {'✅' if s.get('comment', False) else '❌'} ◂ کامنت\n"
    t += f"  {'✅' if s.get('birthday', False) else '❌'} ◂ تولد\n"
    t += f"  {'✅' if s.get('alert', False) else '❌'} ◂ هشدار\n"
    t += "\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
    return t

def build_panel_buttons(s, user_id):
    """دکمه‌های رنگی پنل سلف"""
    P = ButtonStyle.PRIMARY    # 🔵 آبی
    G = ButtonStyle.SUCCESS    # 🟢 سبز
    R = ButtonStyle.DANGER     # 🔴 قرمز

    # ایموجی‌های هر بخش (اگر None باشد، ایموجی یونیکد پیش‌فرض استفاده می‌شود)
    E = EMOJI

    rows = [
        # ظاهری
        [make_btn(f"🎨 کلاسیک {'🟢' if s.get('classic', True) else '🔴'}",
                  f"self_toggle_classic_{user_id}", P),
         make_btn(f"✨ مدرن {'🟢' if s.get('modern', False) else '🔴'}",
                  f"self_toggle_modern_{user_id}", P)],
        [make_btn(f"🇮🇷 فارسی {'🟢' if s.get('persian', True) else '🔴'}",
                  f"self_toggle_persian_{user_id}", G),
         make_btn(f"🇬🇧 انگلیسی {'🟢' if s.get('english', False) else '🔴'}",
                  f"self_toggle_english_{user_id}", G)],
        [make_btn(f"🌍 منطقه {'🟢' if s.get('region', True) else '🔴'}",
                  f"self_toggle_region_{user_id}", P),
         make_btn(f"🌐 سلف همگانی {'🟢' if s.get('public_self', False) else '🔴'}",
                  f"self_toggle_public_self_{user_id}", P)],
        # اطلاعات
        [make_btn(f"📝 بیوگرافی {'🟢' if s.get('bio', False) else '🔴'}",
                  f"self_toggle_bio_{user_id}", G),
         make_btn(f"👤 اسم {'🟢' if s.get('name_setting', False) else '🔴'}",
                  f"self_toggle_name_{user_id}", G)],
        [make_btn(f"📊 آنالیتیک {'🟢' if s.get('analytics', False) else '🔴'}",
                  f"self_toggle_analytics_{user_id}", P),
         make_btn(f"ℹ️ درباره {'🟢' if s.get('about', False) else '🔴'}",
                  f"self_toggle_about_{user_id}", P)],
        [make_btn(f"🏷️ عنوان {'🟢' if s.get('title', False) else '🔴'}",
                  f"self_toggle_title_{user_id}", P),
         make_btn(f"🔒 آنتی لاگین {'🟢' if s.get('anti_login', False) else '🔴'}",
                  f"self_toggle_anti_login_{user_id}", R)],
        # قابلیت‌ها
        [make_btn(f"⏰ ساعت {'🟢' if s.get('clock_enabled', False) else '🔴'}",
                  f"self_toggle_clock_{user_id}", G),
         make_btn(f"👁️ خودخوان {'🟢' if s.get('auto_read', False) else '🔴'}",
                  f"self_toggle_auto_read_{user_id}", G)],
        [make_btn(f"💬 پاسخ خودکار {'🟢' if s.get('auto_reply', False) else '🔴'}",
                  f"self_toggle_auto_reply_{user_id}", P),
         make_btn(f"🛡️ ضد توهین {'🟢' if s.get('anti_insult', False) else '🔴'}",
                  f"self_toggle_anti_insult_{user_id}", R)],
        [make_btn(f"🎬 پیام انیمیشنی {'🟢' if s.get('animated_msg', False) else '🔴'}",
                  f"self_toggle_animated_msg_{user_id}", P),
         make_btn(f"🤖 منشی هوشمند {'🟢' if s.get('smart_secretary', False) else '🔴'}",
                  f"self_toggle_smart_secretary_{user_id}", P)],
        [make_btn(f"⚙️ خودکار {'🟢' if s.get('auto_setting', False) else '🔴'}",
                  f"self_toggle_auto_{user_id}", P),
         make_btn(f"🖼️ بنر {'🟢' if s.get('banner', False) else '🔴'}",
                  f"self_toggle_banner_{user_id}", P)],
        [make_btn(f"💭 کامنت {'🟢' if s.get('comment', False) else '🔴'}",
                  f"self_toggle_comment_{user_id}", P),
         make_btn(f"🎂 تولد {'🟢' if s.get('birthday', False) else '🔴'}",
                  f"self_toggle_birthday_{user_id}", G)],
        [make_btn(f"🔔 هشدار {'🟢' if s.get('alert', False) else '🔴'}",
                  f"self_toggle_alert_{user_id}", R)],
        # کنترل
        [make_btn("🔄 بروزرسانی", f"self_refresh_{user_id}", P),
         make_btn("✖️ بستن پنل", f"self_close_{user_id}", R)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def send_self_panel(client, user_id, chat_id, message_id=None):
    try:
        s = db_get_self_settings(user_id)
        text = build_panel_text(s)
        buttons = build_panel_buttons(s, user_id)
        if message_id:
            try:
                await client.edit_message(chat_id, message_id, text,
                                          buttons=buttons, parse_mode='markdown')
                return message_id
            except Exception as e:
                print(f"خطا در ویرایش: {e}")
        sent = await client.send_message(chat_id, text, buttons=buttons,
                                         parse_mode='markdown')
        return sent.id
    except Exception as e:
        print(f"خطا در ارسال پنل: {e}")
        return None

async def show_self_panel(client, event):
    try:
        user_id = event.sender_id
        if not has_active_subscription(user_id):
            try:
                await client.send_message(event.message.peer_id,
                    "**❌ شما اشتراک فعال ندارید!**\n**💳 لطفاً اشتراک خریداری کنید.**",
                    parse_mode='markdown')
            except: pass
            return
        try:
            await client.delete_messages(event.message.peer_id, [event.message.id])
        except Exception as e:
            print(f"حذف پیام ناموفق: {e}")
        await send_self_panel(client, user_id, event.message.peer_id)
    except Exception as e:
        print(f"خطا در نمایش پنل: {e}")

async def handle_self_callback(event, client):
    try:
        data = event.data.decode('utf-8')
        parts = data.split('_')
        if len(parts) < 3: return
        action = parts[1]
        user_id = int(parts[2])
        s = db_get_self_settings(user_id)
        toggle_map = {
            'clock': 'clock_enabled', 'auto_read': 'auto_read',
            'auto_reply': 'auto_reply', 'anti_insult': 'anti_insult',
            'animated_msg': 'animated_msg', 'smart_secretary': 'smart_secretary',
            'bio': 'bio', 'name': 'name_setting', 'analytics': 'analytics',
            'about': 'about', 'title': 'title', 'anti_login': 'anti_login',
            'auto': 'auto_setting', 'banner': 'banner', 'comment': 'comment',
            'birthday': 'birthday', 'alert': 'alert',
            'classic': 'classic', 'modern': 'modern',
            'persian': 'persian', 'english': 'english',
            'region': 'region', 'public_self': 'public_self'
        }
        if action in toggle_map:
            key = toggle_map[action]
            s[key] = not s.get(key, False)
            if key == 'classic' and s['classic']: s['modern'] = False
            elif key == 'modern' and s['modern']: s['classic'] = False
            if key == 'persian' and s['persian']: s['english'] = False
            elif key == 'english' and s['english']: s['persian'] = False
            db_update_self_settings(user_id, s)
            if key == 'clock_enabled':
                set_clock_status(user_id, s['clock_enabled'])
                if s['clock_enabled']:
                    asyncio.create_task(set_clock_on_profile(user_id))
                else:
                    asyncio.create_task(remove_clock_from_profile(user_id))
            await send_self_panel(client, user_id, event.chat_id, event.message_id)
            await event.answer("✅ تغییر اعمال شد!")
            return
        if action == 'refresh':
            await send_self_panel(client, user_id, event.chat_id, event.message_id)
            await event.answer("🔄 پنل بروزرسانی شد!")
            return
        if action == 'close':
            try:
                await client.delete_messages(event.chat_id, [event.message_id])
            except: pass
            await event.answer("✖️ پنل بسته شد!")
            return
    except Exception as e:
        print(f"خطا در هندلر کال‌بک سلف: {e}")
        try: await event.answer("❌ خطا!")
        except: pass

# ==================== SELF CLIENT ====================
async def start_salf_client(user_id):
    try:
        sd = get_user_session(user_id)
        if not sd: return False
        if user_id in salf_clients:
            try: await salf_clients[user_id].disconnect()
            except: pass
            del salf_clients[user_id]
        if user_id in self_tasks:
            self_tasks[user_id].cancel()
            try: await self_tasks[user_id]
            except: pass
            del self_tasks[user_id]

        client = TelegramClient(f"sessions/user_{user_id}", sd['api_id'], sd['api_hash'])
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect(); return False
        me = await client.get_me()
        my_id = me.id
        salf_clients[user_id] = client

        @client.on(events.NewMessage)
        async def message_handler(event):
            try:
                if event.sender_id != my_id: return
                msg = event.message
                if not msg or not msg.text: return
                text = msg.text.strip()
                if text in ("پنل", ".پنل", "/panel", "/پنل", "Panel", "panel"):
                    await show_self_panel(client, event); return
                if text in (".بلاک", "بلاک", "/block", "/بلاک"):
                    await handle_self_block(client, event, my_id); return
            except Exception as e:
                print(f"خطا در هندلر پیام سلف: {e}")

        @client.on(events.NewMessage(incoming=True))
        async def incoming_handler(event):
            try:
                msg = event.message
                if not msg or not msg.text: return
                if msg.text.strip() not in (".بلاک", "بلاک", "/block", "/بلاک"): return
                await handle_self_block(client, event, my_id, is_incoming=True)
            except Exception as e:
                print(f"خطا در هندلر ورودی: {e}")

        @client.on(events.CallbackQuery)
        async def callback_handler(event):
            await handle_self_callback(event, client)

        async def run_client():
            try: await client.run_until_disconnected()
            except Exception as e: print(f"کلاینت قطع شد: {e}")

        task = asyncio.create_task(run_client())
        self_tasks[user_id] = task
        print(f"✅ سلف کاربر {user_id} راه‌اندازی شد")
        return True
    except Exception as e:
        print(f"خطا در شروع سلف {user_id}: {e}")
        return False

async def start_all_salf_clients():
    for session in db_get_all_sessions():
        try: await start_salf_client(session[0])
        except Exception as e: print(f"خطا: {e}")
        await asyncio.sleep(0.5)

# ==================== بلاک ====================
async def handle_self_block(client, event, self_user_id, is_incoming=False):
    try:
        msg = event.message
        target = None
        if msg.is_reply:
            try:
                replied = await event.get_reply_message()
                if replied and replied.sender_id and replied.sender_id != self_user_id:
                    target = await client.get_entity(replied.sender_id)
            except Exception as e: print(f"خطا در ریپلای: {e}")
        if not target and event.is_private:
            try:
                peer = await event.get_chat()
                if peer and peer.id != self_user_id: target = peer
            except Exception as e: print(f"خطا در peer: {e}")
        if not target:
            try: await event.reply("▸ کاربری برای بلاک پیدا نشد.")
            except: pass
            return
        await client(BlockRequest(id=target.id))
        name = getattr(target, 'first_name', '') or getattr(target, 'username', '') or str(target.id)
        try: await event.reply(f"▸ کاربر {name} بلاک شد!")
        except:
            try: await client.send_message(event.chat_id, f"▸ کاربر {name} بلاک شد!")
            except: pass
    except Exception as e: print(f"خطا در بلاک: {e}")

# ==================== CLOCK ====================
async def set_clock_on_profile(user_id):
    try:
        if not get_clock_status(user_id): return False
        sd = get_user_session(user_id)
        if not sd: return False
        if sd['api_id'] > 2147483647: return False
        client = TelegramClient(f"sessions/user_{user_id}", sd['api_id'], sd['api_hash'])
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect(); return False
        me = await client.get_me()
        fn = me.first_name or ""; ln = me.last_name or ""
        current_name = f"{fn} {ln}".strip() or (me.username or "کاربر")
        iran_tz = pytz.timezone('Asia/Tehran')
        time_str = datetime.now(iran_tz).strftime('%H:%M')
        clean_name = re.sub(r'\s*\d{2}:\d{2}$', '', current_name).strip()
        new_name = f"{clean_name} {time_str}".strip()
        if new_name != current_name:
            try:
                await client(UpdateProfileRequest(first_name=new_name))
                await client.disconnect(); return True
            except:
                await client.disconnect(); return False
        await client.disconnect(); return True
    except: return False

async def remove_clock_from_profile(user_id):
    try:
        sd = get_user_session(user_id)
        if not sd: return False
        if sd['api_id'] > 2147483647: return False
        client = TelegramClient(f"sessions/user_{user_id}", sd['api_id'], sd['api_hash'])
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect(); return False
        me = await client.get_me()
        fn = me.first_name or ""; ln = me.last_name or ""
        current_name = f"{fn} {ln}".strip() or (me.username or "کاربر")
        clean_name = re.sub(r'\s*\d{2}:\d{2}$', '', current_name).strip()
        if clean_name != current_name:
            try:
                await client(UpdateProfileRequest(first_name=clean_name))
                await client.disconnect(); return True
            except:
                await client.disconnect(); return False
        await client.disconnect(); return True
    except: return False

async def clock_loop(user_id):
    last_minute = None
    while True:
        try:
            if not get_clock_status(user_id):
                await asyncio.sleep(30); continue
            current_minute = datetime.now(pytz.timezone('Asia/Tehran')).strftime('%H:%M')
            if current_minute != last_minute:
                await set_clock_on_profile(user_id)
                last_minute = current_minute
            await asyncio.sleep(30)
        except asyncio.CancelledError: break
        except Exception as e:
            print(f"خطا در حلقه ساعت {user_id}: {e}")
            await asyncio.sleep(30)

# ==================== SERVER INFO ====================
async def get_server_info():
    try:
        ping_time = None
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "3", "-W", "2", "8.8.8.8",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate(timeout=5)
            if proc.returncode == 0:
                out = stdout.decode()
                m = re.search(r'avg\s*=\s*(\d+\.?\d*)/(\d+\.?\d*)/(\d+\.?\d*)', out)
                if m: ping_time = float(m.group(2))
                else:
                    m2 = re.search(r'time[=<](\d+\.?\d*)\s*ms', out)
                    if m2: ping_time = float(m2.group(1))
        except: pass
        if ping_time is None:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2); st = time.time()
                sock.connect(("8.8.8.8", 53)); et = time.time()
                sock.close(); ping_time = (et - st) * 1000
            except: pass
        cpu = f"{psutil.cpu_percent(interval=0.5):.1f}%"
        mem = psutil.virtual_memory()
        mem_info = f"{mem.percent:.1f}% ({mem.used // (1024**3)}GB / {mem.total // (1024**3)}GB)"
        disk = psutil.disk_usage('/')
        disk_info = f"{disk.percent:.1f}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)"
        boot = psutil.boot_time()
        up = time.time() - boot
        d = int(up // 86400); h = int((up % 86400) // 3600); mi = int((up % 3600) // 60)
        if d > 0: uptime = f"{d} روز، {h} ساعت، {mi} دقیقه"
        elif h > 0: uptime = f"{h} ساعت، {mi} دقیقه"
        else: uptime = f"{mi} دقیقه"
        if ping_time is None: status = "🔴 قطع"
        elif ping_time < 50: status = "🟢 عالی"
        elif ping_time < 100: status = "🟢 آنلاین"
        elif ping_time < 200: status = "🟡 هشدار"
        else: status = "🔴 ضعیف"
        return {'status': status, 'ping': f"{ping_time:.1f} ms" if ping_time else "❌ نامشخص",
                'cpu': cpu, 'memory': mem_info, 'disk': disk_info,
                'os': platform.system() + " " + platform.release(), 'uptime': uptime}
    except:
        return {'status': "🟢 آنلاین", 'ping': "📶 متصل", 'cpu': "نامشخص",
                'memory': "نامشخص", 'disk': "نامشخص", 'os': platform.system(),
                'uptime': "نامشخص"}

def get_host_expiry():
    try:
        start = datetime(2026, 7, 28); total = 30; today = datetime.now()
        passed = (today - start).days; left = max(0, total - passed)
        return {'days_left': left, 'total_days': total,
                'expiry_date': (start + timedelta(days=total)).strftime('%Y-%m-%d'),
                'start_date': start.strftime('%Y-%m-%d'),
                'percent': (left / total) * 100 if left > 0 else 0}
    except:
        return {'days_left': 26, 'total_days': 30, 'expiry_date': "2026-08-27",
                'start_date': "2026-07-28", 'percent': 86.6}

# ==================== BOT SETUP ====================
router = Router()
bot: Bot = None

# ==================== /start ====================
@router.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    user_id = user.id
    db_add_user(user_id, user.username, user.first_name, user.last_name)
    if is_user_banned(user_id):
        await message.answer("▸ شما از طرف مدیریت مسدود شده‌اید!\n▸ در صورت نیاز با پشتیبانی تماس بگیرید.")
        return
    if user_id in user_states: del user_states[user_id]
    if user_id in user_menu_mode: del user_menu_mode[user_id]
    mention = f"@{user.username}" if user.username else user.first_name

    if is_admin(user_id):
        text = (f"⬢ درود {mention} به پنل ریپر سلف خوش آمدید.\n\n"
                "◆ در این پنل می‌توانید ربات را کنترل و مدیریت کنید.\n\n"
                "▸ لطفاً از منوی زیر انتخاب نمایید.")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [make_btn("⚙️ تنظیمات", "admin_settings", ButtonStyle.PRIMARY)],
            [make_btn("📊 آمار کل", "admin_stats", ButtonStyle.PRIMARY)],
            [make_btn("📡 پینگ", "admin_ping", ButtonStyle.SUCCESS),
             make_btn("⏳ اعتبار هاست", "admin_host", ButtonStyle.SUCCESS)],
            [make_btn("👥 منوی کاربران", "admin_users_menu", ButtonStyle.PRIMARY)],
        ])
        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            await send_user_main_menu_msg(message, user)
            return
    except: pass

    text = ("▸ برای دسترسی به خدمات ما، ابتدا باید در کانال زیر عضو شوید.\n"
            "▸ پس از عضویت، روی دکمه «عضو شدم» کلیک کنید.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("🔗 ریپر سلف", "https://t.me/ReaperSelfChannel", ButtonStyle.PRIMARY)],
        [make_btn("✅ عضو شدم", "check_membership", ButtonStyle.SUCCESS)],
    ])
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def send_user_main_menu_msg(message: Message, user):
    user_id = user.id
    mention = f"@{user.username}" if user.username else user.first_name
    rem = get_remaining_days(user_id)
    has_sub = has_active_subscription(user_id)
    verified = is_user_verified(user_id)
    text = (f"⬢ سلام {mention} به ربات ریپر سلف خوش آمدید!\n\n"
            "◆ در این ربات می‌توانید از پشتیبانی، خرید، نصب ربات سلف بهره ببرید!\n\n"
            "▸ اگر سوالی دارید از بخش پشتیبانی استفاده کنید.")
    rows = [
        [make_btn("👨‍💻 پشتیبانی", "support", ButtonStyle.PRIMARY)],
        [make_btn("🤔 سلف چیست؟", "what_is_self", ButtonStyle.PRIMARY),
         make_btn("📣 کانال ما", "https://t.me/ReaperSelfChannel", ButtonStyle.SUCCESS)],
        [make_btn(f"📅 انقضا شما: ({rem} روز)", "expiry", ButtonStyle.SUCCESS)],
    ]
    if verified:
        rows.append([make_btn("✅ احراز هویت شده", "verified_already", ButtonStyle.SUCCESS)])
    else:
        rows.append([make_btn("✔️ احراز هویت", "verify", ButtonStyle.SUCCESS)])
    rows.append([make_btn("💳 خرید اشتراک", "buy_subscription", ButtonStyle.SUCCESS)])
    rows.append([make_btn("💶 خرید با کد", "buy_with_code", ButtonStyle.SUCCESS)])
    if has_sub:
        rows.append([make_btn("🔑 ورود سلف", "salf_login", ButtonStyle.PRIMARY)])
    rows.append([make_btn("💎 نرخ", "rate", ButtonStyle.PRIMARY)])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

# ==================== CALLBACKS ====================
@router.callback_query(F.data == "check_membership")
async def cb_check_membership(q: CallbackQuery):
    user_id = q.from_user.id
    if is_user_banned(user_id):
        await q.message.edit_text("▸ شما از طرف مدیریت مسدود شده‌اید!")
        return
    if is_admin(user_id):
        await cb_admin_back(q); return
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            await q.message.delete()
            await send_user_main_menu_msg(q.message, q.from_user)
        else:
            await q.answer("❌ هنوز عضو نشده‌اید!", show_alert=True)
    except:
        await q.answer("❌ خطا در بررسی عضویت!", show_alert=True)

@router.callback_query(F.data == "admin_back")
async def cb_admin_back(q: CallbackQuery):
    user_id = q.from_user.id
    if user_id in user_states: del user_states[user_id]
    if user_id in admin_salf_data: del admin_salf_data[user_id]
    mention = f"@{q.from_user.username}" if q.from_user.username else q.from_user.first_name
    text = (f"⬢ درود {mention} به پنل ریپر سلف خوش آمدید.\n\n"
            "◆ در این پنل می‌توانید ربات را کنترل و مدیریت کنید.\n\n"
            "▸ لطفاً از منوی زیر انتخاب نمایید.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("⚙️ تنظیمات", "admin_settings", ButtonStyle.PRIMARY)],
        [make_btn("📊 آمار کل", "admin_stats", ButtonStyle.PRIMARY)],
        [make_btn("📡 پینگ", "admin_ping", ButtonStyle.SUCCESS),
         make_btn("⏳ اعتبار هاست", "admin_host", ButtonStyle.SUCCESS)],
        [make_btn("👥 منوی کاربران", "admin_users_menu", ButtonStyle.PRIMARY)],
    ])
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "admin_settings")
async def cb_admin_settings(q: CallbackQuery):
    mention = f"@{q.from_user.username}" if q.from_user.username else q.from_user.first_name
    text = (f"⬢ درود {mention} به بخش تنظیمات پنل مدیریت خوش آمدید.\n\n"
            "▸ لطفاً یکی از گزینه‌های زیر را انتخاب کنید.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("➕ ساختن کد سلف", "admin_create_code", ButtonStyle.SUCCESS),
         make_btn("✖️ باطل کردن کد", "admin_cancel_code", ButtonStyle.DANGER)],
        [make_btn("🚫 مسدود کردن", "admin_block_user", ButtonStyle.DANGER),
         make_btn("✅ آزاد کردن", "admin_unblock_user", ButtonStyle.SUCCESS)],
        [make_btn("📤 انتقال انقضا", "admin_transfer_credit", ButtonStyle.PRIMARY),
         make_btn("📉 کسر انقضا", "admin_deduct_credit", ButtonStyle.DANGER)],
        [make_btn("🔑 ورود سلف", "admin_salf_login", ButtonStyle.PRIMARY),
         make_btn("🚪 خروج سلف", "admin_salf_logout", ButtonStyle.DANGER)],
        [make_btn("🔙 بازگشت", "admin_back", ButtonStyle.PRIMARY)],
    ])
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "admin_settings_back")
async def cb_admin_settings_back(q: CallbackQuery):
    await cb_admin_settings(q)

@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(q: CallbackQuery):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users'); total = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM users WHERE is_verified = 1'); ver = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM users WHERE is_banned = 1'); ban = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM codes'); tc = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM codes WHERE used = 1'); uc = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM sessions'); ts = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM support_tickets WHERE status = "open"'); ot = c.fetchone()[0]
    conn.close()
    text = ("⬢ آمار کل ربات\n\n"
            f"◆ کل کاربران: {total}\n"
            f"◆ احراز شده: {ver}\n"
            f"◆ مسدود: {ban}\n"
            f"◆ کل کدها: {tc}\n"
            f"◆ کدهای استفاده شده: {uc}\n"
            f"◆ کدهای باقی‌مانده: {tc - uc}\n"
            f"◆ سشن‌ها: {ts}\n"
            f"◆ تیکت‌های باز: {ot}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("🔄 بروزرسانی", "admin_stats", ButtonStyle.PRIMARY)],
        [make_btn("🔙 بازگشت", "admin_back", ButtonStyle.PRIMARY)],
    ])
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "admin_ping")
async def cb_admin_ping(q: CallbackQuery):
    si = await get_server_info()
    text = ("◆ وضعیت پینگ هاست\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
            f"◆ وضعیت: {si['status']}\n"
            f"◆ پینگ: {si['ping']}\n"
            f"◆ CPU: {si['cpu']}\n"
            f"◆ RAM: {si['memory']}\n"
            f"◆ Disk: {si['disk']}\n"
            f"◆ OS: {si['os']}\n"
            f"◆ آپ‌تایم: {si['uptime']}\n"
            "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("🔄 بروزرسانی", "admin_ping", ButtonStyle.SUCCESS)],
        [make_btn("🔙 بازگشت", "admin_back", ButtonStyle.PRIMARY)],
    ])
    try: await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except: pass

@router.callback_query(F.data == "admin_host")
async def cb_admin_host(q: CallbackQuery):
    hi = get_host_expiry()
    filled = int((hi['percent'] / 100) * 10) if hi['percent'] > 0 else 0
    bar = "█" * filled + "░" * (10 - filled)
    text = ("◆ اطلاعات اعتبار هاست\n\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
            f"◆ شروع: {hi['start_date']}\n"
            f"◆ انقضا: {hi['expiry_date']}\n"
            f"◆ باقی‌مانده: {hi['days_left']} روز\n"
            f"◆ وضعیت: {bar} {hi['percent']:.1f}%\n"
            "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰")
    if hi['days_left'] <= 0: text += "\n\n⚠ هاست منقضی شده!"
    elif hi['days_left'] <= 5: text += "\n\n⚠ هاست به زودی منقضی می‌شود!"
    else: text += "\n\n▸ هاست فعال است."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("🔄 بروزرسانی", "admin_host", ButtonStyle.SUCCESS)],
        [make_btn("🔙 بازگشت", "admin_back", ButtonStyle.PRIMARY)],
    ])
    try: await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except: pass

@router.callback_query(F.data == "admin_users_menu")
async def cb_admin_users_menu(q: CallbackQuery):
    user = q.from_user
    user_id = user.id
    mention = f"@{user.username}" if user.username else user.first_name
    rem = get_remaining_days(user_id)
    has_sub = has_active_subscription(user_id)
    verified = is_user_verified(user_id)
    text = (f"⬢ سلام {mention} به ربات ریپر سلف خوش آمدید!\n\n"
            "◆ در این ربات می‌توانید از پشتیبانی، خرید، نصب ربات سلف بهره ببرید!\n\n"
            "▸ اگر سوالی دارید از بخش پشتیبانی استفاده کنید.")
    rows = [
        [make_btn("👨‍💻 پشتیبانی", "support", ButtonStyle.PRIMARY)],
        [make_btn("🤔 سلف چیست؟", "what_is_self", ButtonStyle.PRIMARY),
         make_btn("📣 کانال ما", "https://t.me/ReaperSelfChannel", ButtonStyle.SUCCESS)],
        [make_btn(f"📅 انقضا شما: ({rem} روز)", "expiry", ButtonStyle.SUCCESS)],
    ]
    if verified:
        rows.append([make_btn("✅ احراز هویت شده", "verified_already", ButtonStyle.SUCCESS)])
    else:
        rows.append([make_btn("✔️ احراز هویت", "verify", ButtonStyle.SUCCESS)])
    rows.append([make_btn("💳 خرید اشتراک", "buy_subscription", ButtonStyle.SUCCESS)])
    rows.append([make_btn("💶 خرید با کد", "buy_with_code", ButtonStyle.SUCCESS)])
    if has_sub:
        rows.append([make_btn("🔑 ورود سلف", "salf_login", ButtonStyle.PRIMARY)])
    rows.append([make_btn("💎 نرخ", "rate", ButtonStyle.PRIMARY)])
    if is_admin(user_id):
        rows.append([make_btn("🎈 پنل مدیریت", "admin_back", ButtonStyle.DANGER)])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "back_from_user_menu")
async def cb_back_from_user_menu(q: CallbackQuery):
    user_id = q.from_user.id
    if user_id in user_states: del user_states[user_id]
    await cb_admin_users_menu(q)

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(q: CallbackQuery):
    if is_admin(q.from_user.id):
        await cb_admin_back(q)
    else:
        await cb_back_from_user_menu(q)

# ==================== USER FUNCS ====================
@router.callback_query(F.data == "support")
async def cb_support(q: CallbackQuery):
    user_id = q.from_user.id
    if is_user_banned(user_id):
        await q.message.edit_text("▸ شما مسدود شده‌اید!")
        return
    support_mode[user_id] = True
    text = ("⬢ شما به بخش پشتیبانی متصل شدید.\n\n"
            "⚠ از ارسال اسپم خودداری کنید.\n\n"
            "▸ پیام خود را ارسال کنید.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("✖️ لغو اتصال", "disconnect_support", ButtonStyle.DANGER)],
        [make_btn("🔙 بازگشت", "main_menu", ButtonStyle.PRIMARY)],
    ])
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "disconnect_support")
async def cb_disconnect_support(q: CallbackQuery):
    user_id = q.from_user.id
    if user_id in support_mode: del support_mode[user_id]
    text = "⬢ اتصال با پشتیبانی قطع شد."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("🔙 بازگشت", "main_menu", ButtonStyle.PRIMARY)],
    ])
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "what_is_self")
async def cb_what_is_self(q: CallbackQuery):
    text = ("⬢ سلف چیست؟\n\n"
            "◆ رباتی که روی اکانت شما نصب می‌شود و امکانات خاصی می‌دهد.\n\n"
            "▸ ساعت روی بیو و اسم\n"
            "▸ خوانده شدن خودکار\n"
            "▸ پاسخ خودکار\n"
            "▸ ضد توهین\n"
            "▸ پیام انیمیشنی\n"
            "▸ منشی هوشمند\n"
            "▸ و...\n\n📍 @ReaperSelfChannel")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("🔙 بازگشت", "back_from_user_menu", ButtonStyle.PRIMARY)],
    ])
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "rate")
async def cb_rate(q: CallbackQuery):
    text = ("⬢ نرخ سلف:\n\n"
            "▸ ۱ ماهه: 100,000 تومان\n"
            "▸ ۲ ماهه: 150,000 تومان\n"
            "▸ ۳ ماهه: 200,000 تومان\n"
            "▸ ۴ ماهه: 250,000 تومان\n"
            "▸ ۵ ماهه: 300,000 تومان\n"
            "▸ ۶ ماهه: 350,000 تومان\n\n"
            "📍 @ReaperSelfChannel")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("🔙 بازگشت", "back_from_user_menu", ButtonStyle.PRIMARY)],
    ])
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "expiry")
async def cb_expiry(q: CallbackQuery):
    user_id = q.from_user.id
    rem = get_remaining_days(user_id)
    exp = get_expiry_date(user_id)
    if rem > 0:
        await q.answer(f"📅 انقضا: {exp} ({rem} روز)", show_alert=True)
    else:
        await q.answer("⏳ اشتراک فعال نیست!", show_alert=True)

@router.callback_query(F.data == "verified_already")
async def cb_verified_already(q: CallbackQuery):
    await q.answer("✅ شما قبلاً احراز هویت شده‌اید!", show_alert=True)

@router.callback_query(F.data == "verify")
async def cb_verify(q: CallbackQuery):
    user_id = q.from_user.id
    if is_user_verified(user_id):
        await q.answer("✅ قبلاً احراز شده‌اید!", show_alert=True)
        return
    text = "⬢ منوی احراز هویت\n\n▸ یکی از گزینه‌ها را انتخاب کنید:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("✖️ حذف کارت", "delete_card", ButtonStyle.DANGER)],
        [make_btn("➕ کارت جدید", "new_card", ButtonStyle.SUCCESS)],
        [make_btn("🔙 بازگشت", "back_from_user_menu", ButtonStyle.PRIMARY)],
    ])
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "delete_card")
async def cb_delete_card(q: CallbackQuery):
    await q.answer("✖️ کارت شما حذف شد!", show_alert=True)

@router.callback_query(F.data == "new_card")
async def cb_new_card(q: CallbackQuery):
    user_states[q.from_user.id] = "waiting_for_verify_photo"
    text = ("⬢ احراز هویت\n\n"
            "⚠ نکات:\n"
            "1️⃣ شماره کارت و نام صاحب کارت خوانا باشد.\n"
            "2️⃣ تاریخ اعتبار و CVV2 را بپوشانید.\n"
            "3️⃣ فقط با همین کارت می‌توانید خرید کنید.\n\n"
            "▸ لطفاً عکس کارت را ارسال کنید.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("🔙 بازگشت", "back_to_verify", ButtonStyle.PRIMARY)],
    ])
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "back_to_verify")
async def cb_back_to_verify(q: CallbackQuery):
    if q.from_user.id in user_states: del user_states[q.from_user.id]
    await cb_verify(q)

@router.callback_query(F.data == "buy_subscription")
async def cb_buy_subscription(q: CallbackQuery):
    user_id = q.from_user.id
    if not is_user_verified(user_id):
        text = "⚠ برای خرید ابتدا احراز هویت کنید."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [make_btn("✔️ احراز هویت", "verify", ButtonStyle.SUCCESS)],
            [make_btn("🔙 بازگشت", "back_from_user_menu", ButtonStyle.PRIMARY)],
        ])
        await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return
    text = "▸ مدت اشتراک را انتخاب کنید:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("📆 ۱ ماهه — 100 هزار", "buy_1_month", ButtonStyle.SUCCESS)],
        [make_btn("📆 ۲ ماهه — 150 هزار", "buy_2_month", ButtonStyle.SUCCESS)],
        [make_btn("📆 ۳ ماهه — 200 هزار", "buy_3_month", ButtonStyle.SUCCESS)],
        [make_btn("📆 ۴ ماهه — 250 هزار", "buy_4_month", ButtonStyle.SUCCESS)],
        [make_btn("📆 ۵ ماهه — 300 هزار", "buy_5_month", ButtonStyle.SUCCESS)],
        [make_btn("📆 ۶ ماهه — 350 هزار", "buy_6_month", ButtonStyle.SUCCESS)],
        [make_btn("🔙 بازگشت", "back_from_user_menu", ButtonStyle.PRIMARY)],
    ])
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

for i, price in [(1,100),(2,150),(3,200),(4,250),(5,300),(6,350)]:
    async def handler(q: CallbackQuery, _p=price):
        await q.answer(f"💳 لطفاً مبلغ {_p} هزار تومان را واریز کنید!", show_alert=True)
    router.callback_query(F.data == f"buy_{i}_month")(handler)

@router.callback_query(F.data == "buy_with_code")
async def cb_buy_with_code(q: CallbackQuery):
    user_states[q.from_user.id] = "waiting_for_activation_code"
    text = "▸ لطفاً کد انقضای خریداری شده خود را ارسال کنید."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("🔙 بازگشت", "back_from_user_menu", ButtonStyle.PRIMARY)],
    ])
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

# ==================== SELF LOGIN (User) ====================
@router.callback_query(F.data == "salf_login")
async def cb_salf_login(q: CallbackQuery):
    user_id = q.from_user.id
    if is_user_banned(user_id):
        await q.answer("🚫 مسدود شده‌اید!", show_alert=True); return
    if not has_active_subscription(user_id):
        await q.answer("❌ اشتراک فعال ندارید!", show_alert=True); return
    if get_user_session(user_id):
        await q.answer("🔑 قبلاً وارد شده‌اید!", show_alert=True); return
    user_states[user_id] = "waiting_salf_phone"
    salf_login_data[user_id] = {}
    text = ("⬢ ورود به سلف\n\n"
            "▸ شماره موبایل خود را با کد کشور وارد کنید.\n"
            "▸ مثال: +989123456789")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("🔙 بازگشت", "back_from_user_menu", ButtonStyle.PRIMARY)],
    ])
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

# ==================== MESSAGE HANDLER ====================
@router.message()
async def handle_any_message(message: Message):
    user_id = message.from_user.id
    if is_user_banned(user_id):
        await message.answer("▸ شما مسدود شده‌اید!")
        return
    if user_id in user_states and str(user_states[user_id]).startswith("replying_to_"):
        await handle_admin_reply_message(message)
        return
    if user_id in support_mode:
        await handle_support_message(message)
        return
    if user_id in user_states:
        st = user_states[user_id]
        if st == "waiting_for_verify_photo": await handle_verify_photo(message); return
        if st == "waiting_for_card_number": await handle_verify_card_number(message); return
        if st == "waiting_for_activation_code": await handle_activation_code(message); return
        if st == "waiting_salf_phone": await handle_salf_phone(message); return
        if st == "waiting_salf_api_id": await handle_salf_api_id(message); return
        if st == "waiting_salf_api_hash": await handle_salf_api_hash(message); return
        if st == "waiting_salf_code": await handle_salf_code(message); return
        if st == "waiting_salf_password": await handle_salf_password(message); return
        if st == "waiting_for_block_user": await handle_block_user(message); return
        if st == "waiting_for_unblock_user": await handle_unblock_user(message); return
        if st == "waiting_for_transfer_credit": await handle_transfer_credit(message); return
        if st == "waiting_for_deduct_credit": await handle_deduct_credit(message); return
        if st == "waiting_for_code_days": await handle_code_days(message); return
        if st == "waiting_for_cancel_code": await handle_cancel_code(message); return
        if st == "admin_waiting_phone": await admin_handle_salf_phone(message); return
        if st == "admin_waiting_user_id": await admin_handle_salf_user_id(message); return
        if st == "admin_waiting_api_id": await admin_handle_salf_api_id(message); return
        if st == "admin_waiting_api_hash": await admin_handle_salf_api_hash(message); return
        if st == "admin_waiting_code": await admin_handle_salf_code(message); return
        if st == "admin_waiting_password": await admin_handle_salf_password(message); return
        if st == "admin_waiting_logout_phone": await admin_handle_salf_logout_phone(message); return

# ==================== SUPPORT MSG ====================
async def handle_support_message(message: Message):
    user = message.from_user
    user_id = user.id
    mention = f"@{user.username}" if user.username else user.first_name
    text = message.text or message.caption or "پیام بدون متن"
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('INSERT INTO support_tickets (user_id, username, message, created_date) VALUES (?, ?, ?, ?)',
              (user_id, mention, text, datetime.now().isoformat()))
    ticket_id = c.lastrowid
    conn.commit(); conn.close()
    iran = datetime.now(pytz.timezone('Asia/Tehran'))
    for admin_id in ADMIN_IDS:
        try:
            admin_text = (f"⬢ پیام جدید پشتیبانی\n\n"
                          f"◆ تیکت: {ticket_id}\n◆ کاربر: {mention}\n"
                          f"◆ آیدی: {user_id}\n◆ متن:\n<code>{text}</code>\n\n"
                          f"◆ {iran.strftime('%H:%M')} - {iran.strftime('%Y-%m-%d')}")
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [make_btn("💬 پاسخ", f"reply_{user_id}", ButtonStyle.PRIMARY)],
                [make_btn("🚫 بلاک", f"block_{user_id}", ButtonStyle.DANGER)],
            ])
            await bot.send_message(admin_id, admin_text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except: pass
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("✖️ لغو", "disconnect_support", ButtonStyle.DANGER)],
    ])
    await message.answer("⬢ پیام شما ارسال شد. منتظر پاسخ باشید.", reply_markup=kb)

# ==================== ADMIN REPLY ====================
@router.callback_query(F.data.startswith("reply_"))
async def cb_reply(q: CallbackQuery):
    target = int(q.data.split("_")[1])
    user_states[q.from_user.id] = f"replying_to_{target}"
    await q.message.edit_text("⬢ پاسخ خود را ارسال کنید.")

@router.callback_query(F.data.startswith("block_"))
async def cb_block(q: CallbackQuery):
    target = int(q.data.split("_")[1])
    if not is_user_banned(target):
        ban_user(target)
        try: await bot.send_message(target, "▸ شما مسدود شده‌اید!")
        except: pass
        await q.message.edit_text(f"⬢ کاربر {target} مسدود شد.")
    else:
        await q.message.edit_text(f"⚠ کاربر {target} قبلاً مسدود بود.")

async def handle_admin_reply_message(message: Message):
    uid = message.from_user.id
    if uid not in user_states: return
    target = int(user_states[uid].split("_")[2])
    try:
        if message.text:
            await bot.send_message(target, f"⬢ پاسخ پشتیبانی:\n\n{message.text}")
        elif message.photo:
            await bot.send_photo(target, message.photo[-1].file_id,
                                 caption=f"⬢ پاسخ پشتیبانی:\n\n{message.caption or ''}")
        elif message.document:
            await bot.send_document(target, message.document.file_id,
                                    caption=f"⬢ پاسخ پشتیبانی:\n\n{message.caption or ''}")
        elif message.video:
            await bot.send_video(target, message.video.file_id,
                                 caption=f"⬢ پاسخ پشتیبانی:\n\n{message.caption or ''}")
        await message.answer("✅ پاسخ ارسال شد.")
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")
    del user_states[uid]

# ==================== VERIFY FLOW ====================
async def handle_verify_photo(message: Message):
    uid = message.from_user.id
    if not message.photo:
        await message.answer("❌ فقط عکس بفرستید!"); return
    pending_verify[uid] = {'photo_id': message.photo[-1].file_id}
    user_states[uid] = "waiting_for_card_number"
    await message.answer("⬢ عکس دریافت شد. شماره کارت 16 رقمی را بفرستید.")

async def handle_verify_card_number(message: Message):
    uid = message.from_user.id
    card = re.sub(r'[^0-9]', '', message.text or "")
    if len(card) != 16:
        await message.answer("❌ شماره کارت باید 16 رقم باشد."); return
    user = message.from_user
    mention = f"@{user.username}" if user.username else user.first_name
    photo_id = pending_verify.get(uid, {}).get('photo_id')
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('''INSERT INTO verify_requests (user_id, username, card_number, photo_id, request_date)
                 VALUES (?, ?, ?, ?, ?)''',
              (uid, mention, card, photo_id, datetime.now().isoformat()))
    rid = c.lastrowid
    conn.commit(); conn.close()
    iran = datetime.now(pytz.timezone('Asia/Tehran'))
    for admin_id in ADMIN_IDS:
        try:
            txt = (f"⬢ درخواست احراز هویت\n\n"
                   f"◆ درخواست: {rid}\n◆ کاربر: {mention}\n◆ آیدی: {uid}\n"
                   f"◆ کارت: <code>{card}</code>\n\n"
                   f"◆ {iran.strftime('%H:%M')} - {iran.strftime('%Y-%m-%d')}")
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [make_btn("✅ پذیرفتن", f"accept_verify_{rid}", ButtonStyle.SUCCESS),
                 make_btn("✖️ رد", f"reject_verify_{rid}", ButtonStyle.DANGER)],
                [make_btn("🚫 بلاک", f"block_{uid}", ButtonStyle.DANGER),
                 make_btn("💬 پاسخ", f"reply_{uid}", ButtonStyle.PRIMARY)],
            ])
            if photo_id:
                await bot.send_photo(admin_id, photo_id, caption=txt, reply_markup=kb, parse_mode=ParseMode.HTML)
            else:
                await bot.send_message(admin_id, txt, reply_markup=kb, parse_mode=ParseMode.HTML)
        except: pass
    await message.answer("⬢ درخواست ارسال شد. منتظر تایید باشید.")
    if uid in pending_verify: del pending_verify[uid]
    if uid in user_states: del user_states[uid]

@router.callback_query(F.data.startswith("accept_verify_"))
async def cb_accept_verify(q: CallbackQuery):
    rid = int(q.data.split("_")[2])
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT user_id, username FROM verify_requests WHERE id = ?', (rid,))
    r = c.fetchone(); conn.close()
    if r:
        uid, uname = r
        if not is_user_verified(uid):
            verify_user(uid)
            try: await bot.send_message(uid, "🎉 احراز هویت شما تایید شد!")
            except: pass
            await q.message.edit_text(f"✅ کاربر {uname} احراز شد.")
        else:
            await q.message.edit_text("⚠ قبلاً احراز شده.")
    else:
        await q.message.edit_text("❌ درخواست یافت نشد.")

@router.callback_query(F.data.startswith("reject_verify_"))
async def cb_reject_verify(q: CallbackQuery):
    rid = int(q.data.split("_")[2])
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT user_id, username FROM verify_requests WHERE id = ?', (rid,))
    r = c.fetchone(); conn.close()
    if r:
        uid, uname = r
        try: await bot.send_message(uid, "✖️ درخواست احراز هویت رد شد.")
        except: pass
        await q.message.edit_text(f"✖️ درخواست {uname} رد شد.")
    else:
        await q.message.edit_text("❌ یافت نشد.")

# ==================== ACTIVATION CODE ====================
async def handle_activation_code(message: Message):
    uid = message.from_user.id
    code = (message.text or "").strip().upper()
    data, err = validate_code(code)
    if not data:
        await message.answer(err); return
    if use_code(code, uid):
        rem = get_remaining_days(uid)
        exp = get_expiry_date(uid)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [make_btn("🔙 بازگشت", "back_from_user_menu", ButtonStyle.PRIMARY)],
        ])
        await message.answer(f"⬢ کد فعال شد!\n\n◆ {data['days']} روز اضافه شد.\n"
                             f"◆ انقضا: {exp}\n◆ باقی‌مانده: {rem} روز",
                             reply_markup=kb, parse_mode=ParseMode.HTML)
        del user_states[uid]

# ==================== SELF LOGIN STEPS ====================
async def handle_salf_phone(message: Message):
    uid = message.from_user.id
    phone = (message.text or "").strip()
    if not re.match(r'^\+?[0-9]{10,15}$', phone):
        await message.answer("❌ شماره صحیح نیست. مثال: +989123456789"); return
    salf_login_data[uid]['phone'] = phone
    user_states[uid] = "waiting_salf_api_id"
    await message.answer("⬢ مرحله 2/4 — API ID را وارد کنید.")

async def handle_salf_api_id(message: Message):
    uid = message.from_user.id
    try:
        api_id = int((message.text or "").strip())
        if api_id > 2147483647: raise ValueError
    except:
        await message.answer("❌ API ID باید عدد باشد."); return
    salf_login_data[uid]['api_id'] = api_id
    user_states[uid] = "waiting_salf_api_hash"
    await message.answer("⬢ مرحله 3/4 — API Hash را وارد کنید.")

async def handle_salf_api_hash(message: Message):
    uid = message.from_user.id
    api_hash = (message.text or "").strip()
    if len(api_hash) < 20:
        await message.answer("❌ API Hash نامعتبر."); return
    salf_login_data[uid]['api_hash'] = api_hash
    user_states[uid] = "waiting_salf_code"
    try:
        data = salf_login_data[uid]
        client = TelegramClient(f"sessions/user_{uid}", data['api_id'], data['api_hash'])
        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(data['phone'])
            salf_login_data[uid]['client'] = client
            await message.answer("⬢ مرحله 4/4 — کد به این صورت بفرستید: <code>1.2.3.4.5</code>",
                                 parse_mode=ParseMode.HTML)
        else:
            await client.disconnect()
            await message.answer("❌ قبلاً ثبت شده.")
            del user_states[uid]; del salf_login_data[uid]
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")
        del user_states[uid]; del salf_login_data[uid]

async def handle_salf_code(message: Message):
    uid = message.from_user.id
    code = (message.text or "").replace('.', '').replace(' ', '').strip()
    if not code.isdigit():
        await message.answer("❌ کد را به صورت 1.2.3.4.5 بفرستید."); return
    try:
        data = salf_login_data[uid]
        client = data['client']
        try:
            await client.sign_in(data['phone'], code)
        except SessionPasswordNeededError:
            user_states[uid] = "waiting_salf_password"
            await message.answer("⚠ اکانت 2FA دارد. پسورد را وارد کنید."); return
        me = await client.get_me()
        full = f"{me.first_name or ''} {me.last_name or ''}".strip() or (me.username or "کاربر")
        session_string = client.session.save()
        db_save_session(uid, session_string, data['phone'], data['api_hash'], data['api_id'])
        set_clock_status(uid, True)
        asyncio.create_task(start_salf_client(uid))
        await message.answer(f"⬢ ورود موفق!\n◆ {full}\n◆ سلف فعال شد.\n"
                             "▸ برای پنل، کلمه «پنل» را بنویسید.")
        del user_states[uid]; del salf_login_data[uid]
    except PhoneCodeInvalidError:
        await message.answer("❌ کد نامعتبر.")
    except PhoneCodeExpiredError:
        await message.answer("⏳ کد منقضی شد. دوباره درخواست دهید.")
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")
        del user_states[uid]; del salf_login_data[uid]

async def handle_salf_password(message: Message):
    uid = message.from_user.id
    pw = (message.text or "").strip()
    if not pw:
        await message.answer("❌ پسورد خالی."); return
    try:
        data = salf_login_data[uid]
        client = data['client']
        await client.sign_in(password=pw)
        me = await client.get_me()
        full = f"{me.first_name or ''} {me.last_name or ''}".strip() or (me.username or "کاربر")
        session_string = client.session.save()
        db_save_session(uid, session_string, data['phone'], data['api_hash'], data['api_id'])
        set_clock_status(uid, True)
        asyncio.create_task(start_salf_client(uid))
        await message.answer(f"⬢ ورود موفق!\n◆ {full}")
        del user_states[uid]; del salf_login_data[uid]
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")
        del user_states[uid]; del salf_login_data[uid]

# ==================== ADMIN: BLOCK/UNBLOCK ====================
async def handle_block_user(message: Message):
    uid = message.from_user.id
    try: target = int((message.text or "").strip())
    except: await message.answer("❌ آیدی نامعتبر."); return
    if target in ADMIN_IDS:
        await message.answer("❌ نمی‌توانید ادمین را بلاک کنید."); return
    if not is_user_banned(target):
        ban_user(target)
        try: await bot.send_message(target, "▸ شما مسدود شدید.")
        except: pass
        await message.answer(f"⬢ کاربر {target} مسدود شد.")
    else:
        await message.answer(f"⚠ قبلاً مسدود بود.")
    del user_states[uid]

async def handle_unblock_user(message: Message):
    uid = message.from_user.id
    try: target = int((message.text or "").strip())
    except: await message.answer("❌ آیدی نامعتبر."); return
    if is_user_banned(target):
        unban_user(target)
        try: await bot.send_message(target, "⬢ از مسدودیت آزاد شدید.")
        except: pass
        await message.answer(f"⬢ کاربر {target} آزاد شد.")
    else:
        await message.answer(f"⚠ در لیست مسدودین نیست.")
    del user_states[uid]

# ==================== ADMIN: CREDIT ====================
async def handle_transfer_credit(message: Message):
    uid = message.from_user.id
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("❌ فرمت: آیدی_مبدا آیدی_مقصد روز"); return
    try: from_id, to_id, days = int(parts[0]), int(parts[1]), int(parts[2])
    except: await message.answer("❌ اعداد نامعتبر."); return
    if days <= 0: await message.answer("❌ روز باید > 0."); return
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT remaining_days FROM users WHERE user_id = ?', (from_id,))
    fr = c.fetchone()
    if not fr or not fr[0] or fr[0] < days:
        conn.close(); await message.answer("⚠ مبدا اشتراک کافی ندارد."); return
    new_from = fr[0] - days
    new_from_exp = (datetime.now() + timedelta(days=new_from)).isoformat() if new_from else None
    c.execute('UPDATE users SET remaining_days = ?, expiry_date = ? WHERE user_id = ?',
              (new_from, new_from_exp, from_id))
    c.execute('SELECT remaining_days FROM users WHERE user_id = ?', (to_id,))
    tr = c.fetchone()
    if tr and tr[0] is not None:
        new_to = tr[0] + days
        new_to_exp = (datetime.now() + timedelta(days=new_to)).isoformat()
        c.execute('UPDATE users SET remaining_days = ?, expiry_date = ? WHERE user_id = ?',
                  (new_to, new_to_exp, to_id))
    else:
        new_to_exp = (datetime.now() + timedelta(days=days)).isoformat()
        c.execute('INSERT INTO users (user_id, remaining_days, expiry_date) VALUES (?, ?, ?)',
                  (to_id, days, new_to_exp))
    conn.commit(); conn.close()
    await message.answer(f"⬢ {days} روز از {from_id} به {to_id} منتقل شد.")
    del user_states[uid]

async def handle_deduct_credit(message: Message):
    uid = message.from_user.id
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("❌ فرمت: آیدی روز"); return
    try: target, days = int(parts[0]), int(parts[1])
    except: await message.answer("❌ اعداد نامعتبر."); return
    if days <= 0: await message.answer("❌ روز باید > 0."); return
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT remaining_days FROM users WHERE user_id = ?', (target,))
    tr = c.fetchone()
    if not tr or not tr[0]:
        conn.close(); await message.answer("⚠ اشتراک فعال ندارد."); return
    new_days = max(0, tr[0] - days)
    new_exp = (datetime.now() + timedelta(days=new_days)).isoformat() if new_days else None
    c.execute('UPDATE users SET remaining_days = ?, expiry_date = ? WHERE user_id = ?',
              (new_days, new_exp, target))
    conn.commit(); conn.close()
    await message.answer(f"⬢ {days} روز از {target} کسر شد.")
    del user_states[uid]

# ==================== ADMIN: CODES ====================
async def handle_code_days(message: Message):
    uid = message.from_user.id
    try:
        days = int((message.text or "").strip())
        if not (1 <= days <= 100000): raise ValueError
    except:
        await message.answer("❌ عدد بین 1 تا 100000."); return
    new_code, exp = create_new_code(days)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("🔙 بازگشت", "admin_settings_back", ButtonStyle.PRIMARY)],
    ])
    await message.answer(f"⬢ کد ساخته شد!\n\n▸ <code>{new_code}</code>\n\n"
                         f"▸ انقضا: {exp.strftime('%Y-%m-%d')}\n▸ {days} روز",
                         reply_markup=kb, parse_mode=ParseMode.HTML)
    del user_states[uid]

async def handle_cancel_code(message: Message):
    uid = message.from_user.id
    code = (message.text or "").strip().upper()
    r = db_get_code(code)
    if not r:
        await message.answer("❌ کد یافت نشد."); return
    if r[4] == 1:
        await message.answer("❌ استفاده شده و قابل باطل نیست."); return
    db_delete_code(code)
    await message.answer(f"⬢ کد <code>{code}</code> باطل شد.", parse_mode=ParseMode.HTML)
    del user_states[uid]

# ==================== ADMIN: SELF LOGIN ====================
@router.callback_query(F.data == "admin_salf_login")
async def cb_admin_salf_login(q: CallbackQuery):
    admin_salf_data[q.from_user.id] = {}
    user_states[q.from_user.id] = "admin_waiting_phone"
    text = ("⬢ ورود سلف (مدیریت)\n\n▸ شماره کاربر را با کد کشور وارد کنید.\n"
            "▸ مثال: +989123456789")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("🔙 بازگشت", "admin_settings_back", ButtonStyle.PRIMARY)],
    ])
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "admin_salf_logout")
async def cb_admin_salf_logout(q: CallbackQuery):
    user_states[q.from_user.id] = "admin_waiting_logout_phone"
    text = "⬢ خروج سلف\n\n▸ شماره تلفن را وارد کنید."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("🔙 بازگشت", "admin_settings_back", ButtonStyle.PRIMARY)],
    ])
    await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def admin_handle_salf_phone(message: Message):
    uid = message.from_user.id
    phone = (message.text or "").strip()
    if not re.match(r'^\+?[0-9]{10,15}$', phone):
        await message.answer("❌ شماره نامعتبر."); return
    admin_salf_data[uid]['phone'] = phone
    user_states[uid] = "admin_waiting_user_id"
    await message.answer("⬢ مرحله 2/5 — آیدی عددی کاربر را وارد کنید.")

async def admin_handle_salf_user_id(message: Message):
    uid = message.from_user.id
    try: target = int((message.text or "").strip())
    except: await message.answer("❌ آیدی نامعتبر."); return
    admin_salf_data[uid]['target_user_id'] = target
    user_states[uid] = "admin_waiting_api_id"
    await message.answer("⬢ مرحله 3/5 — API ID را وارد کنید.")

async def admin_handle_salf_api_id(message: Message):
    uid = message.from_user.id
    try:
        api_id = int((message.text or "").strip())
        if api_id > 2147483647: raise ValueError
    except: await message.answer("❌ API ID نامعتبر."); return
    admin_salf_data[uid]['api_id'] = api_id
    user_states[uid] = "admin_waiting_api_hash"
    await message.answer("⬢ مرحله 4/5 — API Hash را وارد کنید.")

async def admin_handle_salf_api_hash(message: Message):
    uid = message.from_user.id
    api_hash = (message.text or "").strip()
    if len(api_hash) < 20:
        await message.answer("❌ API Hash نامعتبر."); return
    admin_salf_data[uid]['api_hash'] = api_hash
    user_states[uid] = "admin_waiting_code"
    try:
        data = admin_salf_data[uid]
        client = TelegramClient(f"sessions/admin_{uid}", data['api_id'], data['api_hash'])
        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(data['phone'])
            admin_salf_data[uid]['client'] = client
            await message.answer("⬢ مرحله 5/5 — کد را به صورت <code>1.2.3.4.5</code> بفرستید.",
                                 parse_mode=ParseMode.HTML)
        else:
            await client.disconnect()
            await message.answer("❌ قبلاً ثبت شده.")
            del user_states[uid]; del admin_salf_data[uid]
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")
        del user_states[uid]; del admin_salf_data[uid]

async def admin_handle_salf_code(message: Message):
    uid = message.from_user.id
    code = (message.text or "").replace('.', '').replace(' ', '').strip()
    if not code.isdigit():
        await message.answer("❌ کد را به صورت 1.2.3.4.5 بفرستید."); return
    try:
        data = admin_salf_data[uid]
        client = data['client']
        try:
            await client.sign_in(data['phone'], code)
        except SessionPasswordNeededError:
            user_states[uid] = "admin_waiting_password"
            await message.answer("⚠ 2FA فعال است. پسورد را وارد کنید."); return
        me = await client.get_me()
        full = f"{me.first_name or ''} {me.last_name or ''}".strip() or (me.username or "کاربر")
        session_string = client.session.save()
        db_save_session(data['target_user_id'], session_string, data['phone'],
                        data['api_hash'], data['api_id'])
        await client.disconnect()
        set_clock_status(data['target_user_id'], True)
        asyncio.create_task(start_salf_client(data['target_user_id']))
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [make_btn("🔙 بازگشت", "admin_settings_back", ButtonStyle.PRIMARY)],
        ])
        await message.answer(f"⬢ ورود موفق!\n◆ {full}\n◆ {data['phone']}\n"
                             f"◆ کاربر: {data['target_user_id']}",
                             reply_markup=kb, parse_mode=ParseMode.HTML)
        del user_states[uid]; del admin_salf_data[uid]
    except PhoneCodeInvalidError:
        await message.answer("❌ کد نامعتبر.")
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")
        del user_states[uid]; del admin_salf_data[uid]

async def admin_handle_salf_password(message: Message):
    uid = message.from_user.id
    pw = (message.text or "").strip()
    if not pw:
        await message.answer("❌ پسورد خالی."); return
    try:
        data = admin_salf_data[uid]
        client = data['client']
        await client.sign_in(password=pw)
        me = await client.get_me()
        full = f"{me.first_name or ''} {me.last_name or ''}".strip() or (me.username or "کاربر")
        session_string = client.session.save()
        db_save_session(data['target_user_id'], session_string, data['phone'],
                        data['api_hash'], data['api_id'])
        await client.disconnect()
        set_clock_status(data['target_user_id'], True)
        asyncio.create_task(start_salf_client(data['target_user_id']))
        await message.answer(f"⬢ ورود موفق!\n◆ {full}")
        del user_states[uid]; del admin_salf_data[uid]
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")
        del user_states[uid]; del admin_salf_data[uid]

async def admin_handle_salf_logout_phone(message: Message):
    uid = message.from_user.id
    phone = (message.text or "").strip()
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute('SELECT user_id, api_hash, api_id FROM sessions WHERE phone = ?', (phone,))
    r = c.fetchone(); conn.close()
    if not r:
        await message.answer("❌ کاربری یافت نشد."); del user_states[uid]; return
    target, api_hash, api_id = r
    try:
        client = TelegramClient(f"sessions/user_{target}", api_id, api_hash)
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            fn = me.first_name or ""; ln = me.last_name or ""
            cur = f"{fn} {ln}".strip() or (me.username or "کاربر")
            clean = re.sub(r'\s*\d{2}:\d{2}$', '', cur).strip()
            if clean != cur:
                try: await client(UpdateProfileRequest(first_name=clean))
                except: pass
        await client.disconnect()
    except: pass
    delete_user_session(target); set_clock_status(target, False)
    if target in salf_clients:
        try: await salf_clients[target].disconnect()
        except: pass
        del salf_clients[target]
    if target in self_tasks:
        self_tasks[target].cancel(); del self_tasks[target]
    try: await bot.send_message(target, "🚪 سلف از اکانت شما خارج شد.")
    except: pass
    await message.answer(f"⬢ خروج از {target} انجام شد.")
    del user_states[uid]

# ==================== STARTUP ====================
async def on_startup(bot_: Bot):
    global bot
    bot = bot_
    print("🔄 ری‌استارت سلف‌ها...")
    asyncio.create_task(start_all_salf_clients())
    for s in db_get_all_sessions():
        if get_clock_status(s[0]):
            asyncio.create_task(clock_loop(s[0]))
    print("✅ آماده.")

async def main():
    global bot
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await on_startup(bot)
    print("🤖 ربات در حال اجراست...")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
