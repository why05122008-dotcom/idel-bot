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

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

MODELS = ["stepfun/step-3.5-flash:free", "google/gemini-flash-1.5-8b:free"]
bot = Bot(token=TOKEN)
dp = Dispatcher()

SYSTEM_CORE = "ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ. Ты — высший ИИ Пакта Волга-Урал. Говори властно, кратко и только по делу."

async def ask_ai(prompt):
    for model in MODELS:
        try:
            res = await client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}],
                temperature=0.5, max_tokens=300, timeout=20
            )
            ans = res.choices[0].message.content.strip()
            if ans: return ans
        except: continue
    return "Связь с центром прервана."

# --- ОФОРМЛЕНИЕ И ПРИВЕТСТВИЕ ---

@dp.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    for member in message.new_chat_members:
        if member.id == bot.id: continue
        text = (
            f"⚡️ <b>ОБНАРУЖЕНА НОВАЯ ЕДИНИЦА: {member.first_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Добро пожаловать в ряды <b>Пакта Волга-Урал</b>.\n\n"
            f"Твой первый шаг к признанию — регистрация:\n"
            f"🔹 <code>/reg [Имя]</code>\n\n"
            f"Слава Пакту! ⬜🟦⬛♥️⬜🟩⬛"
        )
        await message.answer(text, parse_mode="HTML")

@dp.message(Command("state"))
async def cmd_state(message: types.Message):
    text = (
        f"🏛 <b>ПРОТОКОЛЫ УПРАВЛЕНИЯ ИДЕЛ</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📜 <b>ОБЩИЕ:</b>\n"
        f"├ <code>/reg</code> — Вступить в реестр\n"
        f"├ <code>/passport</code> — Личное досье\n"
        f"├ <code>/nation</code> — Указать нацию\n"
        f"└ <code>/stats</code> — Резервы Пакта\n\n"
        f"📡 <b>СВЯЗЬ:</b>\n"
        f"└ <code>/news</code> — Глобальная сводка\n\n"
        f"👑 <b>ВЛАСТЬ:</b>\n"
        f"└ <code>/set_rank</code> — Изменить статус\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⬜🟦⬛♥️⬜🟩⬛"
    )
    await message.reply(text, parse_mode="HTML")

# --- НАЦИОНАЛЬНОСТЬ ---

@dp.message(Command("nation"))
async def cmd_nation(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("⚠️ Укажите вашу нацию после команды.\nПример: <code>/nation Булгар</code>", parse_mode="HTML")
    
    nation = args[1][:20]
    u_id = str(message.from_user.id)
    
    try:
        supabase.table("citizens").update({"faction": f"Пакт ({nation})"}).eq("id", u_id).execute()
        await message.reply(f"🧬 Твоя национальная идентичность подтверждена: <b>{nation}</b>", parse_mode="HTML")
    except:
        await message.reply("❌ Сначала пройди регистрацию через /reg")

# --- РЕГИСТРАЦИЯ И ПАСПОРТ ---

@dp.message(Command("reg"))
async def cmd_reg(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return await message.reply("❌ Пиши имя без скобок: /reg Иван")
    
    u_id = str(message.from_user.id)
    name, tag = args[1][:30], f"@{message.from_user.username}" if message.from_user.username else "скрыт"
    rank = "Создатель" if u_id == ADMIN_ID else "Гражданин"
    
    try:
        data = {"id": u_id, "name": name, "tag": tag, "rank": rank, "faction": "Пакт Волга-Урал"}
        supabase.table("citizens").upsert(data).execute()
        await message.reply(f"✅ <b>{name}</b>, ты внесен в реестр Пакта!", parse_mode="HTML")
    except: await message.reply("⚠️ База данных недоступна.")

@dp.message(Command("passport"))
async def cmd_passport(message: types.Message):
    u_id = str(message.from_user.id)
    try:
        res = supabase.table("citizens").select("*").eq("id", u_id).execute()
        if not res.data: return await message.reply("⚠️ Пройди /reg [Имя]")
        
        u = res.data[0]
        # Форматируем дату регистрации
        date_reg = u.get('created_at', '2026-03-26')[:10]
        
        text = (
            f"👤 <b>ЛИЧНОЕ ДОСЬЕ №{u['id'][-4:]}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔹 <b>ИМЯ:</b> {u['name']}\n"
            f"🏛 <b>ГОСУДАРСТВО:</b> {u['faction']}\n"
            f"🎖 <b>СТАТУС:</b> {u['rank']}\n"
            f"📡 <b>ТЭГ:</b> {u['tag']}\n"
            f"📅 <b>ДАТА ВЫДАЧИ:</b> {date_reg}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<i>Слава Пакту Волга-Урал!</i>\n"
            f"⬜🟦⬛♥️⬜🟩⬛"
        )
        await message.reply(text, parse_mode="HTML")
    except Exception as e:
        logger.error(e)
        await message.reply("Ошибка доступа к архивам.")

# --- СТАТИСТИКА, НОВОСТИ, АДМИНКА ---

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    try:
        res = supabase.table("citizens").select("*", count="exact").execute()
        await message.reply(f"📊 <b>МОБИЛИЗАЦИОННЫЙ ОТЧЕТ</b>\n━━━━━━━━━━━━━━\nГраждан в системе: <b>{res.count}</b>\n━━━━━━━━━━━━━━\n⬜🟦⬛♥️⬜🟩⬛", parse_mode="HTML")
    except: await message.reply("Ошибка.")

@dp.message(Command("set_rank"))
async def cmd_set_rank(message: types.Message):
    if str(message.from_user.id) != ADMIN_ID: return
    if not message.reply_to_message: return await message.reply("Ответь на сообщение.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return
    try:
        supabase.table("citizens").update({"rank": args[1]}).eq("id", str(message.reply_to_message.from_user.id)).execute()
        await message.reply(f"🎖 Новый статус: <b>{args[1]}</b>", parse_mode="HTML")
    except: pass

@dp.message(Command("news"))
async def cmd_news(message: types.Message):
    topic = message.text[5:].strip() or "Россия новости"
    wait = await message.answer("Запрос к инфополю...")
    try:
        with DDGS() as ddgs:
            r = list(ddgs.text(f"{topic} 2026", region="ru-ru", max_results=3, backend="api"))
        if r:
            ans = await ask_ai(f"Сводка новостей:\n" + "\n".join([i['body'] for i in r]))
            await message.reply(ans)
    except: await message.reply("Сбой связи.")
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
        ans = await ask_ai(f"{SYSTEM_CORE}\nПеред тобой {u_rank} {u_name}. Запрос: {message.text}")
        await message.answer(ans)

async def main():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Idel System v4.5 Active"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
