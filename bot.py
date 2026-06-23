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
        #  БЕСКОНЕЧНАЯ РАССЫЛКА С ПОКАЗОМ КАЖДОГО СООБЩЕНИЯ
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
                    
                    # =============================================
                    #  ПОКАЗЫВАЕМ КАЖДОЕ ОТПРАВЛЕННОЕ СООБЩЕНИЕ
                    # =============================================
                    await bot.send_message(chat_id, f"📨 {target} | отправлено (цикл #{cycle}, всего: {total_sent})")
                    
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
                
                # =============================================
                #  УВЕДОМЛЕНИЕ О ЖИЗНИ БОТА ВО ВРЕМЯ ОЖИДАНИЯ
                # =============================================
                await bot.send_message(chat_id, f"💤 Ожидание {spam_timer} сек до следующего цикла...")
                
                # РАЗБИВАЕМ ОЖИДАНИЕ НА ЧАСТИ, ЧТОБЫ ПОКАЗЫВАТЬ ПРОГРЕСС
                if spam_timer > 30:
                    steps = min(int(spam_timer // 30), 10)  # максимум 10 уведомлений
                    step_time = spam_timer / steps
                    for i in range(1, steps + 1):
                        if not user_is_spamming.get(user_id, False):
                            break
                        await asyncio.sleep(step_time)
                        remaining = int(spam_timer - (i * step_time))
                        if remaining > 0 and i < steps:
                            await bot.send_message(chat_id, f"⏳ Осталось {remaining} сек до следующего цикла...")
                else:
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