import os
import asyncio
import re
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from supabase import create_client, Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiohttp import web

# ================= КОНФИГ =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
scheduler = AsyncIOScheduler()

MSK_TZ = timezone(timedelta(hours=3))

# ================= ЗАЩИТА И ЭКРАНИРОВАНИЕ =================
def esc(text):
    if not text: return ""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))

async def get_target_id(message: types.Message, args: list):
    if message.reply_to_message:
        return str(message.reply_to_message.from_user.id)
    if args:
        target = args[0].replace("@", "")
        if target.isdigit(): return target
        res = supabase.table("players").select("user_id").eq("username", target).execute()
        if res.data: return res.data[0]['user_id']
    return None

def get_p(uid):
    res = supabase.table("players").select("*").eq("user_id", str(uid)).execute()
    return res.data[0] if res.data else None

# ================= ВЕБ-СЕРВЕР ДЛЯ RENDER =================
async def handle(request):
    return web.Response(text="Idel Bot is Active")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# ================= КОМАНДЫ =================

@dp.message(Command("instruction"))
async def cmd_instruction(message: types.Message):
    text = (
        r"📖 *ИНСТРУКЦИЯ ПАКТА*" + "\n\n"
        r"🚩 *ГОСУДАРСТВО*" + "\n"
        r"• `/create [Имя]` — создать страну" + "\n"
        r"• `/capital [Имя]` — сменить столицу \(10к\)" + "\n"
        r"• `/info [@юзер]` — досье" + "\n\n"
        r"⚔️ *ДИПЛОМАТИЯ*" + "\n"
        r"• `/war [@юзер]` — объявить войну" + "\n"
        r"• `/peace [@юзер]` — заключить мир" + "\n"
        r"• `/attack [Город] [Войска]` — осада" + "\n\n"
        r"💰 *ЭКОНОМИКА*" + "\n"
        r"• `/pay [@юзер] [Сумма]` — перевод"
    )
    await message.reply(text, parse_mode=ParseMode.MARKDOWN_V2)

@dp.message(Command("create"))
async def cmd_create(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2: 
        return await message.reply(r"Введите название страны\!", parse_mode=ParseMode.MARKDOWN_V2)
    
    uid = str(message.from_user.id)
    if get_p(uid): 
        return await message.reply(r"У вас уже есть государство\!", parse_mode=ParseMode.MARKDOWN_V2)
    
    name = args[1][:25]
    supabase.table("players").insert({
        "user_id": uid, "username": message.from_user.username, 
        "state_name": name, "balance": 50000, "army": 1000
    }).execute()
    supabase.table("cities").insert({"owner_id": uid, "name": f"Столица {name}", "is_capital": True}).execute()
    await message.reply(f"🚩 Страна *{esc(name)}* создана\!", parse_mode=ParseMode.MARKDOWN_V2)

@dp.message(Command("war"))
async def cmd_war(message: types.Message):
    args = message.text.split()[1:]
    target_id = await get_target_id(message, args)
    uid = str(message.from_user.id)
    if not target_id or target_id == uid: 
        return await message.reply(r"❌ Ошибка цели\.", parse_mode=ParseMode.MARKDOWN_V2)
    
    supabase.table("wars").insert({"player_a": uid, "player_b": target_id, "status": "active"}).execute()
    await message.reply(r"⚔️ *ВОЙНА ОБЪЯВЛЕНА\!*", parse_mode=ParseMode.MARKDOWN_V2)

@dp.message(Command("pay"))
async def cmd_pay(message: types.Message):
    args = message.text.split()
    try:
        amt = int(args[-1])
        tid = await get_target_id(message, args[:-1])
        uid = str(message.from_user.id)
        
        if tid == uid or amt <= 0:
            return await message.reply(r"❌ Нельзя перевести самому себе\.", parse_mode=ParseMode.MARKDOWN_V2)
        
        s = get_p(uid)
        if s['balance'] < amt:
            return await message.reply(r"Недостаточно золота\.", parse_mode=ParseMode.MARKDOWN_V2)
        
        supabase.table("players").update({"balance": s['balance'] - amt}).eq("user_id", uid).execute()
        target_p = get_p(tid)
        supabase.table("players").update({"balance": target_p['balance'] + amt}).eq("user_id", tid).execute()
        await message.reply(f"💰 Переведено {amt:,} золота\.")
    except Exception:
        await message.reply(r"❌ Ошибка перевода\.", parse_mode=ParseMode.MARKDOWN_V2)

# ================= ЗАПУСК =================
async def tax_job():
    ps = supabase.table("players").select("user_id, balance").execute().data
    if ps:
        for p in ps:
            cs = supabase.table("cities").select("id").eq("owner_id", p['user_id']).execute().data
            if cs:
                new_val = p['balance'] + (len(cs) * 5000)
                supabase.table("players").update({"balance": new_val}).eq("user_id", p['user_id']).execute()

async def main():
    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)
    
    scheduler.add_job(tax_job, 'interval', hours=4)
    scheduler.start()
    
    print("🚀 Идель v8.9 запущена без ошибок отступов!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 
