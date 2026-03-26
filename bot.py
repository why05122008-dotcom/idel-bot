import os, asyncio, logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- КОНФИГ ---
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") 
ADMIN_ID = str(os.getenv("ADMIN_ID", "")).strip()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

MODELS = ["stepfun/step-3.5-flash:free", "google/gemini-flash-1.5-8b:free"]

bot = Bot(token=TOKEN)
dp = Dispatcher()

SYSTEM_CORE = "ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ. Ты ИИ-советник Пакта Волга-Урал. Отвечай кратко, жестко, на русском."

async def ask_ai(prompt):
    for model in MODELS:
        try:
            res = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5, max_tokens=300, timeout=20
            )
            ans = res.choices[0].message.content.strip()
            if ans: return ans
        except: continue
    return "Связь с ядром нестабильна."

# --- ПРИВЕТСТВИЕ НОВЫХ УЧАСТНИКОВ ---

@dp.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    for member in message.new_chat_members:
        if member.id == bot.id: continue
        welcome_text = (
            f"⚡️ <b>Новая боевая единица в чате!</b>\n\n"
            f"Добро пожаловать в Пакт Волга-Урал, {member.first_name}.\n"
            f"Чтобы получить доступ к архивам и статусу, введи команду:\n"
            f"<code>/reg [Твое Имя]</code>"
        )
        await message.answer(welcome_text, parse_mode="HTML")

# --- СТАТИСТИКА ПАКТА ---

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    try:
        res = supabase.table("citizens").select("*", count="exact").execute()
        count = res.count
        await message.reply(f"📊 <b>ОТЧЕТ ПАКТА</b>\n━━━━━━━━━━━━━━\nЗарегистрировано граждан: <b>{count}</b>\nЦель: Доминирование в регионе.", parse_mode="HTML")
    except:
        await message.reply("Ошибка запроса к реестру.")

# --- УПРАВЛЕНИЕ РАНГАМИ ---

@dp.message(Command("set_rank"))
async def cmd_set_rank(message: types.Message):
    if str(message.from_user.id) != ADMIN_ID:
        return await message.reply("❌ Доступ запрещен.")
    if not message.reply_to_message:
        return await message.reply("❌ Ответь на сообщение пользователя.")
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return await message.reply("❌ Укажи ранг.")
    
    new_rank, target_id = args[1], str(message.reply_to_message.from_user.id)
    try:
        supabase.table("citizens").update({"rank": new_rank}).eq("id", target_id).execute()
        await message.reply(f"🎖 Статус обновлен: <b>{new_rank}</b>", parse_mode="HTML")
    except:
        await message.reply("❌ Ошибка. Пользователь в базе?")

# --- РЕГИСТРАЦИЯ И ПАСПОРТ ---

@dp.message(Command("reg"))
async def cmd_reg(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return await message.reply("❌ Формат: /reg [Имя]")
    
    u_id = str(message.from_user.id)
    name, tag = args[1][:30], f"@{message.from_user.username}" if message.from_user.username else "скрыт"
    rank = "Создатель" if u_id == ADMIN_ID else "Гражданин"
    
    try:
        data = {"id": u_id, "name": name, "tag": tag, "rank": rank, "faction": "Пакт Волга-Урал"}
        supabase.table("citizens").upsert(data).execute()
        await message.reply(f"✅ Ты в базе, {name}!")
    except:
        await message.reply("⚠️ Сбой базы.")

@dp.message(Command("passport"))
async def cmd_passport(message: types.Message):
    u_id = str(message.from_user.id)
    try:
        res = supabase.table("citizens").select("*").eq("id", u_id).execute()
        if not res.data: return await message.reply("⚠️ Пройди /reg [Имя]")
        
        u = res.data[0]
        text = (f"🛂 <b>ПАСПОРТ ПАКТА</b>\n━━━━━━━━━━━━━━\n"
                f"👤 <b>Имя:</b> {u['name']}\n🎖 <b>Статус:</b> {u['rank']}\n"
                f"🌐 <b>Фракция:</b> {u['faction']}\n━━━━━━━━━━━━━━")
        await message.reply(text, parse_mode="HTML")
    except: await message.reply("Ошибка архива.")

# --- НОВОСТИ И ЧАТ ---

@dp.message(Command("news"))
async def cmd_news(message: types.Message):
    topic = message.text[5:].strip() or "Россия важные новости"
    wait = await message.answer("Синхронизация...")
    try:
        with DDGS() as ddgs:
            r = list(ddgs.text(f"{topic} 2026", region="ru-ru", max_results=3, backend="api"))
        if r:
            ans = await ask_ai(f"Сводка новостей:\n" + "\n".join([i['body'] for i in r]))
            await message.reply(ans)
    except: await message.reply("Сбой хаба.")
    finally: await bot.delete_message(message.chat.id, wait.message_id)

@dp.message()
async def main_handler(message: types.Message):
    if not message.text: return
    if message.chat.type == 'private' or "идел" in message.text.lower():
        u_id = str(message.from_user.id)
        u_name, u_rank = "Аноним", "Неизвестный"
        try:
            res = supabase.table("citizens").select("name, rank").eq("id", u_id).execute()
            if res.data: u_name, u_rank = res.data[0]['name'], res.data[0]['rank']
        except: pass
        ans = await ask_ai(f"{SYSTEM_CORE}\n{u_rank} {u_name}: {message.text}")
        await message.answer(ans)

async def main():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Idel System v3.5 Online"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main()) 
