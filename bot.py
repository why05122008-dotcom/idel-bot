import os
import asyncio
import random
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from supabase import create_client, Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================= КОНФИГ =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
AI_API_KEY = os.environ.get("AI_API_KEY") # Твой ключ OpenRouter/Gemini

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
scheduler = AsyncIOScheduler()

MSK_TZ = timezone(timedelta(hours=3))

# ================= СИСТЕМНЫЕ ПРОВЕРКИ =================
def is_night_time():
    now = datetime.now(MSK_TZ)
    return 0 <= now.hour < 8

def get_player(uid: str):
    res = supabase.table("players").select("*").eq("user_id", uid).execute()
    return res.data[0] if res.data else None

def check_war(a: str, b: str):
    res = supabase.table("wars").select("*").eq("status", "active").execute()
    for w in res.data:
        if (w['player_a'] == a and w['player_b'] == b) or (w['player_a'] == b and w['player_b'] == a):
            return True
    return False

# ================= МИРОВЫЕ КОМАНДЫ =================

@dp.message(Command("create"))
async def cmd_create(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return await message.reply("❌ Использование: /create [Название]")
    
    uid, name = str(message.from_user.id), args[1]
    if get_player(uid): return await message.reply("🏛 У вас уже есть государство!")

    supabase.table("players").insert({"user_id": uid, "username": message.from_user.username, "state_name": name}).execute()
    supabase.table("cities").insert({"owner_id": uid, "name": f"Столица {name}", "is_capital": True}).execute()
    
    await message.reply(f"🚩 **{name}** основана!\n💰 50,000 золота в казне.\n🪖 1,000 солдат в резерве.\n🏙 Столица построена.", parse_mode="Markdown")

@dp.message(Command("states"))
async def cmd_states(message: types.Message):
    players = supabase.table("players").select("*").execute().data
    cities = supabase.table("cities").select("*").execute().data
    if not players: return await message.reply("Мир пуст.")

    total_gold = sum(p['balance'] for p in players)
    total_army = sum(p['army'] for p in players) + sum(c['garrison'] for c in cities)

    # Сортировка по мощи (баланс + армия)
    players.sort(key=lambda x: x['balance'] + x['army'], reverse=True)

    text = f"🌍 **РЕЕСТР СТРАН ПАКТА**\n━━━━━━━━━━━━━━\n"
    text += f"💰 Общий ВВП: {total_gold:,}\n🪖 Всего войск: {total_army:,}\n━━━━━━━━━━━━━━\n"
    
    for i, p in enumerate(players[:10]):
        medals = ["🥇", "🥈", "🥉"]
        icon = medals[i] if i < 3 else "🚩"
        text += f"{icon} **{p['state_name']}** | 💰 {p['balance']:,}\n"

    await message.reply(text, parse_mode="Markdown")

@dp.message(Command("info"))
async def cmd_info(message: types.Message):
    target = str(message.reply_to_message.from_user.id) if message.reply_to_message else str(message.from_user.id)
    p = get_player(target)
    if not p: return await message.reply("Государство не найдено.")
    
    cts = supabase.table("cities").select("*").eq("owner_id", target).execute().data
    city_list = "\n".join([f"├ 🏙 {c['name']} [Lvl {c['level']}] (Protect: {c['garrison']:,})" for c in cts])
    
    await message.reply(f"📑 **{p['state_name']}** (@{p['username']})\n━━━━━━━━━━━━━━\n💰 Казна: {p['balance']:,}\n🪖 Резерв: {p['army']:,}\n🏙 Города:\n{city_list}", parse_mode="Markdown")

# ================= ЭКОНОМИКА И ВОЙНА =================

@dp.message(Command("army"))
async def cmd_army(message: types.Message):
    uid = str(message.from_user.id)
    p = get_player(uid)
    if not p: return
    
    last = datetime.fromisoformat(p['last_army_claim'].replace('Z', '+00:00'))
    if datetime.now(timezone.utc) - last < timedelta(hours=8):
        return await message.reply("⏳ Солдаты на учениях (доступно раз в 8ч).")

    gain = random.randint(1000, 3000)
    supabase.table("players").update({"army": p['army'] + gain, "last_army_claim": datetime.now(timezone.utc).isoformat()}).eq("user_id", uid).execute()
    await message.reply(f"🪖 Мобилизация завершена: +{gain:,} бойцов!")

@dp.message(Command("upgrade"))
async def cmd_upgrade(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return await message.reply("❌ /upgrade [Название города]")
    
    uid, cname = str(message.from_user.id), args[1]
    p = get_player(uid)
    res = supabase.table("cities").select("*").eq("name", cname).eq("owner_id", uid).execute()
    
    if not res.data: return await message.reply("Город не найден или он не ваш.")
    city = res.data[0]
    
    cost = 50000 if city['level'] == 1 else 150000
    if city['level'] >= 3: return await message.reply("🏰 Максимальный уровень!")
    if p['balance'] < cost: return await message.reply(f"💰 Нужно {cost:,} золота!")

    supabase.table("players").update({"balance": p['balance'] - cost}).eq("user_id", uid).execute()
    supabase.table("cities").update({"level": city['level'] + 1}).eq("id", city['id']).execute()
    await message.reply(f"🏗 Стены города {cname} улучшены до уровня {city['level'] + 1}!")

@dp.message(Command("war"))
async def cmd_war(message: types.Message):
    if is_night_time(): return await message.reply("🌙 Ночное перемирие до 08:00 МСК.")
    if not message.reply_to_message: return await message.reply("Укажите врага через ответ на сообщение.")
    
    a, b = str(message.from_user.id), str(message.reply_to_message.from_user.id)
    if check_war(a, b): return await message.reply("Война уже идет!")
    
    supabase.table("wars").insert({"player_a": a, "player_b": b}).execute()
    await message.reply("⚔️ **УЛЬТИМАТУМ ПРИНЯТ! Состояние войны объявлено.**", parse_mode="Markdown")

@dp.message(Command("attack"))
async def cmd_attack(message: types.Message):
    if is_night_time(): return await message.reply("🌙 Ночь — время для сна, а не для войн.")
    args = message.text.split()
    if len(args) < 3: return await message.reply("❌ /attack [Город] [Число]")
    
    cname, forces = args[1], int(args[2])
    uid = str(message.from_user.id)
    p = get_player(uid)
    
    city_res = supabase.table("cities").select("*").eq("name", cname).execute()
    if not city_res.data: return await message.reply("Город не найден.")
    city = city_res.data[0]
    
    if not check_war(uid, city['owner_id']): return await message.reply("❌ Сначала объявите войну через /war!")
    if p['army'] < forces or forces < 500: return await message.reply("Недостаточно войск (мин. 500).")

    supabase.table("players").update({"army": p['army'] - forces}).eq("user_id", uid).execute()
    end_time = datetime.now(timezone.utc) + timedelta(minutes=60)
    supabase.table("battles").insert({"city_id": city['id'], "attacker_id": uid, "attacker_forces": forces, "end_time": end_time.isoformat(), "chat_id": str(message.chat.id)}).execute()
    
    await message.reply(f"🚨 **ОСАДА {cname.upper()} НАЧАЛАСЬ!**\n🕒 Битва завершится через 60 минут.", parse_mode="Markdown")

@dp.message(Command("protect"))
async def cmd_protect(message: types.Message):
    args = message.text.split()
    if len(args) < 3: return await message.reply("/protect [Город] [Число]")
    
    cname, amt = args[1], int(args[2])
    uid = str(message.from_user.id)
    p = get_player(uid)
    
    res = supabase.table("cities").select("*").eq("name", cname).eq("owner_id", uid).execute()
    if not res.data or p['army'] < amt or amt <= 0: return await message.reply("❌ Ошибка параметров или нехватка войск.")

    supabase.table("players").update({"army": p['army'] - amt}).eq("user_id", uid).execute()
    supabase.table("cities").update({"garrison": res.data[0]['garrison'] + amt}).eq("id", res.data[0]['id']).execute()
    await message.reply(f"🛡 **Protect:** {amt:,} бойцов заняли позиции в {cname}.")

@dp.message(Command("pay"))
async def cmd_pay(message: types.Message):
    if not message.reply_to_message: return await message.reply("Ответьте на сообщение получателя.")
    args = message.text.split()
    if len(args) < 2: return await message.reply("/pay [Сумма]")
    
    amount = int(args[1])
    if amount <= 0: return await message.reply("❌ Сумма должна быть больше нуля.")
    
    sender_id = str(message.from_user.id)
    receiver_id = str(message.reply_to_message.from_user.id)
    
    sender = get_player(sender_id)
    receiver = get_player(receiver_id)
    
    if not sender or not receiver: return await message.reply("Один из игроков не в системе.")
    if sender['balance'] < amount: return await message.reply("Недостаточно золота.")
    if check_war(sender_id, receiver_id): return await message.reply("Нельзя платить врагу во время войны!")

    supabase.table("players").update({"balance": sender['balance'] - amount}).eq("user_id", sender_id).execute()
    supabase.table("players").update({"balance": receiver['balance'] + amount}).eq("user_id", receiver_id).execute()
    await message.reply(f"💰 Переведено {amount:,} золота государству {receiver['state_name']}.")

# ================= ИДЕЛЬ: ИИ ЛОГИКА =================

@dp.message(F.text & ~F.text.startswith("/"))
async def idel_ai_chat(message: types.Message):
    # Если бот в чате, отвечает только на "Идель" или тег
    if message.chat.type != "private":
        if not (message.text.lower().startswith("идель") or f"@{bot.id}" in message.text):
            return
    
    # ТУТ ВАШ СТАРЫЙ КОД ПОДКЛЮЧЕНИЯ К OPENROUTER
    # Просто вставьте свою функцию вызова нейронки
    await message.reply("🤖 *Идель слушает...* (Здесь будет ответ вашего ИИ)", parse_mode="Markdown")

# ================= ФОНОВЫЕ ЗАДАЧИ =================

async def tax_job():
    """Сбор налогов раз в 4 часа"""
    ps = supabase.table("players").select("*").execute().data
    cs = supabase.table("cities").select("*").execute().data
    for p in ps:
        count = sum(1 for c in cs if c['owner_id'] == p['user_id'])
        if count > 0:
            income = count * 5000
            supabase.table("players").update({"balance": p['balance'] + income}).eq("user_id", p['user_id']).execute()

async def battle_job():
    """Разрешение битв каждую минуту"""
    now = datetime.now(timezone.utc)
    bs = supabase.table("battles").select("*").execute().data
    for b in bs:
        if now >= datetime.fromisoformat(b['end_time']).replace(tzinfo=timezone.utc):
            city = supabase.table("cities").select("*").eq("id", b['city_id']).execute().data[0]
            mult = 1.5 if city['level'] == 1 else (2.0 if city['level'] == 2 else 3.0)
            
            # Итоговая мощь защиты
            def_power = (city['garrison'] + b['support_forces']) * mult
            
            if b['attacker_forces'] > def_power:
                # Победа атаки
                supabase.table("cities").update({
                    "owner_id": b['attacker_id'], 
                    "garrison": int(b['attacker_forces'] * 0.4), 
                    "level": 1
                }).eq("id", city['id']).execute()
                msg = f"🔥 **ГОРОД {city['name'].upper()} ПАЛ!**\nЗахватчик установил свою власть. Стены разрушены до 1 уровня."
            else:
                # Победа защиты
                supabase.table("cities").update({"garrison": int(city['garrison'] * 0.6)}).eq("id", city['id']).execute()
                msg = f"🛡 **ОСАДА {city['name'].upper()} ПРОВАЛЕНА!**\nЗащитники выстояли. Агрессор отступил с потерями."
            
            await bot.send_message(b['chat_id'], msg, parse_mode="Markdown")
            supabase.table("battles").delete().eq("id", b['id']).execute()

# ================= ЗАПУСК =================

async def main():
    scheduler.add_job(battle_job, 'interval', minutes=1)
    scheduler.add_job(tax_job, 'interval', hours=4)
    scheduler.start()
    
    print("🚀 Идель: Пакт v7.0 запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 
