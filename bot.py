import os
import asyncio
import random
import re
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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
scheduler = AsyncIOScheduler()

MSK_TZ = timezone(timedelta(hours=3))

# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================
def clean_md(text):
    """Очистка текста от символов, ломающих Markdown"""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))

async def get_target_id(message: types.Message, args: list):
    """Определяет ID цели по реплаю, юзернейму или ID"""
    if message.reply_to_message:
        return str(message.reply_to_message.from_user.id)
    if args:
        target = args[0].replace("@", "")
        if target.isdigit(): return target
        # Поиск в базе по username
        res = supabase.table("players").select("user_id").eq("username", target).execute()
        if res.data: return res.data[0]['user_id']
    return None

def is_night():
    return 0 <= datetime.now(MSK_TZ).hour < 8

def get_p(uid):
    res = supabase.table("players").select("*").eq("user_id", str(uid)).execute()
    return res.data[0] if res.data else None

# ================= КОМАНДЫ УПРАВЛЕНИЯ =================

@dp.message(Command("instruction"))
async def cmd_instruction(message: types.Message):
    text = (
        "📖 **ИНСТРУКЦИЯ**\n\n"
        "🚩 **ОСНОВЫ:**\n"
        "• `/create [Название]` — создать страну.\n"
        "• `/capital [Имя]` — сменить название столицы (10к).\n"
        "• `/info [@юзер/ID]` — разведка данных.\n\n"
        "⚔️ **ВОЙНА:**\n"
        "• `/war [@юзер/ID]` — объявить войну (нужно перед атакой).\n"
        "• `/attack [Город] [Войска]` — начать осаду (60 мин).\n"
        "• `/protect [Город] [Войска]` — усилить гарнизон.\n\n"
        "💰 **ЭКОНОМИКА:**\n"
        "• `/army` — призыв (раз в 8ч).\n"
        "• `/pay [@юзер] [Сумма]` — перевод золота.\n"
        "• `/upgrade [Город]` — уровень стен (до Lvl 3).\n\n"
        "⚠️ *Атаки запрещены с 00:00 до 08:00 МСК.*"
    )
    await message.reply(text, parse_mode="MarkdownV2")

@dp.message(Command("create"))
async def cmd_create(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return await message.reply("Введите название страны!")
    uid = str(message.from_user.id)
    if get_p(uid): return await message.reply("У вас уже есть государство!")
    
    name = args[1][:30]
    supabase.table("players").insert({"user_id": uid, "username": message.from_user.username, "state_name": name}).execute()
    supabase.table("cities").insert({"owner_id": uid, "name": f"Столица {name}", "is_capital": True}).execute()
    await message.reply(f"🚩 Страна **{clean_md(name)}** признана мировым сообществом!", parse_mode="MarkdownV2")

@dp.message(Command("capital"))
async def cmd_capital(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return await message.reply("/capital [Новое название]")
    uid = str(message.from_user.id)
    p = get_p(uid)
    if p['balance'] < 10000: return await message.reply("Смена названия столицы стоит 10,000 золота!")
    
    new_name = args[1][:30]
    supabase.table("players").update({"balance": p['balance'] - 10000}).eq("user_id", uid).execute()
    supabase.table("cities").update({"name": new_name}).eq("owner_id", uid).eq("is_capital", True).execute()
    await message.reply(f"🏙 Столица переименована в **{clean_md(new_name)}**!", parse_mode="MarkdownV2")

@dp.message(Command("war"))
async def cmd_war(message: types.Message):
    if is_night(): return await message.reply("🌙 Ночное перемирие.")
    args = message.text.split()[1:]
    target_id = await get_target_id(message, args)
    
    if not target_id or target_id == str(message.from_user.id):
        return await message.reply("Укажите врага (реплаем, @username или ID).")
    
    res = supabase.table("wars").select("*").eq("player_a", str(message.from_user.id)).eq("player_b", target_id).eq("status", "active").execute()
    if res.data: return await message.reply("Вы уже воюете!")
    
    supabase.table("wars").insert({"player_a": str(message.from_user.id), "player_b": target_id}).execute()
    await message.reply("⚔️ **СОСТОЯНИЕ ВОЙНЫ ОБЪЯВЛЕНО!**", parse_mode="MarkdownV2")

@dp.message(Command("attack"))
async def cmd_attack(message: types.Message):
    if is_night(): return await message.reply("🌙 Ночь.")
    args = message.text.split()
    if len(args) < 3: return await message.reply("/attack [Город] [Число]")
    
    cname, forces = args[1], int(args[2])
    uid = str(message.from_user.id)
    p = get_p(uid)
    
    city = supabase.table("cities").select("*").eq("name", cname).execute().data
    if not city: return await message.reply("Город не найден.")
    
    # Проверка войны (в обе стороны)
    war = supabase.table("wars").select("*").or_(f"and(player_a.eq.{uid},player_b.eq.{city[0]['owner_id']}),and(player_a.eq.{city[0]['owner_id']},player_b.eq.{uid})").eq("status", "active").execute()
    
    if not war.data: return await message.reply("Сначала объявите войну через /war!")
    if p['army'] < forces or forces < 500: return await message.reply("Недостаточно войск.")

    supabase.table("players").update({"army": p['army'] - forces}).eq("user_id", uid).execute()
    end_t = datetime.now(timezone.utc) + timedelta(minutes=60)
    
    sent_msg = await message.reply(f"🚨 **ОСАДА {clean_md(cname.upper())}!**\n🕒 Конец через 60 минут.", parse_mode="MarkdownV2")
    
    supabase.table("battles").insert({
        "city_id": city[0]['id'], "attacker_id": uid, 
        "attacker_forces": forces, "end_time": end_t.isoformat(), 
        "chat_id": str(message.chat.id), "message_id": str(sent_msg.message_id)
    }).execute()

@dp.message(Command("pay"))
async def cmd_pay(message: types.Message):
    args = message.text.split()
    if len(args) < 2: return await message.reply("/pay [@юзер/ID] [Сумма]")
    
    amt = int(args[-1])
    target_id = await get_target_id(message, args[:-1])
    
    if amt <= 0 or not target_id: return await message.reply("Ошибка параметров.")
    
    sender = get_p(message.from_user.id)
    if sender['balance'] < amt: return await message.reply("Недостаточно золота.")
    
    supabase.table("players").update({"balance": sender['balance'] - amt}).eq("user_id", str(message.from_user.id)).execute()
    supabase.table("players").update({"balance": get_p(target_id)['balance'] + amt}).eq("user_id", target_id).execute()
    await message.reply(f"💰 Переведено {amt:,} золота.")

# ================= ШЕДУЛЕР (НАЛОГИ И БИТВЫ) =================

async def tax_job():
    players = supabase.table("players").select("user_id, balance").execute().data
    for p in players:
        count = len(supabase.table("cities").select("id").eq("owner_id", p['user_id']).execute().data)
        if count > 0:
            supabase.table("players").update({"balance": p['balance'] + (count * 5000)}).eq("user_id", p['user_id']).execute()

async def battle_job():
    now = datetime.now(timezone.utc)
    battles = supabase.table("battles").select("*").execute().data
    for b in battles:
        if now >= datetime.fromisoformat(b['end_time']).replace(tzinfo=timezone.utc):
            city = supabase.table("cities").select("*").eq("id", b['city_id']).execute().data[0]
            mult = {1: 1.5, 2: 2.0, 3: 3.0}.get(city['level'], 1.5)
            defense = (city['garrison'] + b['support_forces']) * mult
            
            if b['attacker_forces'] > defense:
                supabase.table("cities").update({"owner_id": b['attacker_id'], "garrison": int(b['attacker_forces']*0.4), "level": 1}).eq("id", city['id']).execute()
                res_text = f"🚩 **{clean_md(city['name'])} захвачен!**"
            else:
                supabase.table("cities").update({"garrison": int(city['garrison']*0.6)}).eq("id", city['id']).execute()
                res_text = f"🛡 **{clean_md(city['name'])} выстоял!**"
            
            await bot.send_message(b['chat_id'], res_text, parse_mode="MarkdownV2")
            supabase.table("battles").delete().eq("id", b['id']).execute()

# ================= ЗАПУСК =================
async def main():
    scheduler.add_job(battle_job, 'interval', minutes=1)
    scheduler.add_job(tax_job, 'interval', hours=4)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 
