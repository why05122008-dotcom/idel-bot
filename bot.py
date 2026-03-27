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
    """Экранирует спецсимволы для MarkdownV2"""
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
        "📖 *ИНСТРУКЦИЯ ПАКТА*\n\n"
        "🚩 *ГОСУДАРСТВО*\n"
        "• `/create [Имя]` — создать страну\n"
        "• `/capital [Имя]` — сменить столицу \(10к\)\n"
        "• `/info [@юзер]` — досье\n\n"
        "⚔️ *ДИПЛОМАТИЯ*\n"
        "• `/war [@юзер]` — объявить войну\n"
        "• `/peace [@юзер]` — заключить мир\n"
        "• `/attack [Город] [Войска]` — осада\n\n"
        "💰 *ЭКОНОМИКА*\n"
        "• `/pay [@юзер] [Сумма]` — перевод"
    )
    await message.reply(text, parse_mode=ParseMode.MARKDOWN_V2)

@dp.message(Command("create"))
async def cmd_create(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return await message.reply("Введите название страны\!")
    uid = str(message.from_user.id)
    if get_p(uid): return await message.reply("У вас уже есть государство\!")
    
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
    if not target_id or target_id == uid: return await message.reply("❌ Ошибка цели\.")
    
    supabase.table("wars").insert({"player_a": uid, "player_b": target_id, "status": "active"}).execute()
    await message.reply("⚔️ *ВОЙНА ОБЪЯВЛЕНА\!*", parse_mode=ParseMode.MARKDOWN_V2)

@dp.message(Command("pay"))
async def cmd_pay(message: types.Message):
    args = message.text.split()
    try:
        amt = int(args[-1])
        tid = await get_target_id(message, args[:-1])
        uid = str(message.from_user.id)
        if tid == uid or amt <= 0: return await message.reply("❌ Нельзя перевести самому себе\.")
        
        s = get_p(uid)
        if s['balance'] < amt: return await message.reply("Недостаточно золота\.")
        
        supabase.table("players").update({"balance": s['balance'] - amt}).eq("user_id", uid).execute()
        target_p = get_p(tid)
        supabase.table("players").update({"balance": target_p['balance'] + amt}).eq("user_id", tid).execute()
        await message.reply(f"💰 Переведено {amt:,} золота\.")
    except: await message.reply("Ошибка перевода\.")

# ================= ЗАПУСК =================
async def tax_job():
    ps = supabase.table("players").select("user_id, balance").execute().data
    for p in ps:
        cs = supabase.table("cities").select("id").eq("owner_id", p['user_id']).execute().data
        if cs:
            supabase.table("players").update({"balance": p['balance'] + (len(cs) * 5000)}).eq("user_id", p['user_id']).execute()

async def main():
    #
