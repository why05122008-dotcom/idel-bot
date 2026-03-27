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

# ================= ТЕХНИЧЕСКИЕ ФУНКЦИИ (ЗАЩИТА) =================
def esc(text):
    """Экранирует спецсимволы для MarkdownV2, чтобы бот не падал"""
    if not text: return ""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))

async def get_target_id(message: types.Message, args: list):
    """Определяет ID цели: Реплай > Username > ID"""
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

def is_night():
    return 0 <= datetime.now(MSK_TZ).hour < 8

# ================= ВЕБ-СЕРВЕР ДЛЯ RENDER (ЧТОБЫ НЕ ПАДАЛ ПОРТ) =================
async def handle(request):
    return web.Response(text="Идель: Пакт Активен")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# ================= КОМАНДЫ ДИПЛОМАТИИ И СТРАНЫ =================

@dp.message(Command("instruction"))
async def cmd_instruction(message: types.Message):
    text = (
        "📖 *ИНСТРУКЦИЯ ПАКТА*\n\n"
        "🚩 *ГОСУДАРСТВО*\n"
        "• `/create [Имя]` — создать страну\n"
        "• `/capital [Имя]` — сменить имя столицы \(10к\)\n"
        "• `/info [@юзер]` — разведка данных\n"
        "• `/states` — мировой рейтинг\n\n"
        "⚔️ *ВОЙНА И МИР*\n"
        "• `/war [@юзер]` — объявить войну\n"
        "• `/peace [@юзер]` — предложить мир\n"
        "• `/attack [Город] [Войска]` — начать осаду\n"
        "• `/protect [Город] [Войска]` — защита города\n\n"
        "💰 *ЭКОНОМИКА*\n"
        "• `/army` — призыв \(раз в 8ч\)\n"
        "• `/pay [@юзер] [Сумма]` — перевод золота\n"
        "• `/upgrade [Город]` — уровень стен\n"
    )
    await message.reply(text, parse_mode=ParseMode.MARKDOWN_V2)

@dp.message(Command("war"))
async def cmd_war(message: types.Message):
    if is_night(): return await message.reply("🌙 Ночное перемирие до 08:00 МСК\.")
    args = message.text.split()[1:]
    target_id = await get_target_id(message, args)
    uid = str(message.from_user.id)
    
    if not target_id or target_id == uid:
        return await message.reply("❌ Нельзя объявить войну самому себе или призраку\.")

    exists = supabase.table("wars").select("*").eq("player_a", uid).eq("player_b", target_id).eq("status", "active").execute()
    if exists.data: return await message.reply("⚔️ Вы уже воюете\!")

    supabase.table("wars").insert({"player_a": uid, "player_b": target_id, "status": "active"}).execute()
    await message.reply(f"⚔️ *СОСТОЯНИЕ ВОЙНЫ ОБЪЯВЛЕНО\!*\nИспользуйте `/attack` для нападения\.", parse_mode=ParseMode.MARKDOWN_V2)

@dp.message(Command("peace"))
async def cmd_peace(message: types.Message):
    args = message.text.split()[1:]
    target_id = await get_target_id(message, args)
    uid = str(message.from_user.id)

    if not target_id or target_id == uid:
        return await message.reply("❌ Вы не воюете с самим собой\.")

    supabase.table("wars").update({"status": "closed"}).or_(f"and(player_a.eq.{uid},player_b.eq.{target_id}),and(player_a.eq.{target_id},player_b.eq.{uid})").execute()
    await message.reply("🤝 *Мир подписан\!* Осады прекращены\.", parse_mode=ParseMode.MARKDOWN_V2)

@dp.message(Command("create"))
async def cmd_create(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return await message.reply("Введите название\!")
    uid = str(message.from_user.id)
    if get_p(uid): return await message.reply("У вас уже есть страна\!")
    
    name = args[1][:25]
    supabase.table("players").insert({"user_id": uid, "username": message.from_user.username, "state_name": name}).execute()
    supabase.table("cities").insert({"owner_id": uid, "name": f"Столица {name}", "is_capital": True}).execute()
    await message.reply(f"🚩 Страна *{esc(name)}* создана\!", parse_mode=ParseMode.MARKDOWN_V2)

@dp.message(Command("info"))
async def cmd_info(message: types.Message):
    args = message.text.split()[1:]
    target_id = await get_target_id(message, args) or str(message.from_user.id)
    p = get_p(target_id)
    if not p: return await message.reply("Страна не найдена\.")
    
    cts = supabase.table("cities").select("*").eq("owner_id", target_id).execute().data
    city_list = "\n".join([f"├ 🏙 {esc(c['name'])} \[Lvl {c['level']}\] \(Гарнизон: {c['garrison']:,}\)" for c in cts])
    
    res = (
        f"📑 *{esc(p['state_name'])}* \(@{esc(p['username'])}\)\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 Казна: {p['balance']:,}\n"
        f"🪖 Резерв: {p['army']:,}\n"
        f"🏙 Города:\n{city_list}"
    )
    await message.reply(res, parse_mode=ParseMode.MARKDOWN_V2)

@dp.message(Command("pay"))
async def cmd_pay(message: types.Message):
    args = message.text.split()
    if len(args) < 2: return await message.reply("Использование: /pay @юзер [сумма]")
    
    try:
        amt = int(args[-1])
        target_id = await get_target_id(message, args[:-1])
    except: return await message.reply("Ошибка ввода\.")

    uid = str(message.from_user.id)
    if not target_id or target_id == uid or amt <= 0: return await message.reply("❌ Некорректный перевод\.")
    
    sender = get_p(uid)
    if sender['balance'] < amt: return await message.reply("Недостаточно золота\.")
    
    supabase.table("players").update({"balance": sender['balance'] - amt}).eq("user_id", uid).execute()
    supabase.table("players").update({"balance": get_p(target_id)['balance'] + amt}).eq("user_id", target_id).execute()
    await message.reply(f"💰 Успешно переведено {amt:,} золота\.")

# ================= ШЕДУЛЕР (НАЛОГИ И БИТВЫ) =================

async def tax_job():
    players = supabase.table("players").select("user_id, balance").execute().data
    for p in players:
        cities = supabase.table("cities").select("id").eq("owner_id", p['user_id']).execute().data
        if cities:
            supabase.table("players").update({"balance": p['balance'] + (len(cities
