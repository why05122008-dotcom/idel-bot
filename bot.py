import os, asyncio, logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS
from supabase import create_client, Client

# Настройка логирования
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

# Твои старые модели ИИ
MODELS = ["stepfun/step-3.5-flash:free", "google/gemini-flash-1.5-8b:free"]

bot = Bot(token=TOKEN)
dp = Dispatcher()

SYSTEM_CORE = "ТЫ — ИДЕЛ. Твой создатель и Президент — ТРАМАДОЛ. Ты — ИИ Пакта Волга-Урал. Говори властно, кратко и только по делу."
FLAGS = "⬜🟦⬛❤️⬜🟩⬛"

async def ask_ai(prompt):
    for model in MODELS:
        try:
            res = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5, max_tokens=300, timeout=15
            )
            ans = res.choices[0].message.content.strip()
            if ans: return ans
        except Exception as e:
            logger.warning(f"Модель {model} недоступна: {e}")
            continue
    return "⚡️ Связь с центральным процессором перегружена. Попробуйте позже."

# --- ПРИВЕТСТВИЕ ---

@dp.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    for member in message.new_chat_members:
        if member.id == bot.id: continue
        text = (
            f"⚡️ <b>ОБНАРУЖЕНА НОВАЯ ЕДИНИЦА: {member.first_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Добро пожаловать в <b>Пакт Волга-Урал</b>.\n\n"
            f"Для легализации в системе используй:\n"
            f"🔹 <code>/reg [Имя]</code>\n\n"
            f"Слава Пакту! {FLAGS}"
        )
        await message.answer(text, parse_mode="HTML")

# --- УПРАВЛЕНИЕ И МЕНЮ ---

@dp.message(Command("state"))
async def cmd_state(message: types.Message):
    text = (
        f"🏛 <b>ПРОТОКОЛЫ УПРАВЛЕНИЯ ИДЕЛ</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📜 <b>ОБЩИЕ:</b>\n"
        f"├ <code>/reg</code> — Вступить в реестр\n"
        f"├ <code>/passport</code> — Личное досье\n"
        f"├ <code>/nation</code> — Указать нацию\n"
        f"└ <code>/stats</code> — Статистика Пакта\n\n"
        f"🛰 <b>СВЯЗЬ (ТЕСТ):</b>\n"
        f"└ <code>/news</code> — Глобальная сводка\n\n"
        f"👑 <b>ВЛАСТЬ:</b>\n"
        f"├ <code>/set_rank</code> — Изменить статус\n"
        f"└ <code>/verify</code> — Президентская печать\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{FLAGS}"
    )
    await message.reply(text, parse_mode="HTML")

# --- СИСТЕМА ГРАЖДАНСТВА ---

@dp.message(Command("reg"))
async def cmd_reg(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return await message.reply("❌ Формат: <code>/reg Имя</code>", parse_mode="HTML")
    
    u_id = str(message.from_user.id)
    name = args[1][:30]
    u_name_t = message.from_user.username
    tag = f"@{u_name_t}" if u_name_t else "скрыт"
    rank = "Президент" if u_id == ADMIN_ID else "Гражданин"
    
    try:
        data = {"id": u_id, "name": name, "tag": tag, "rank": rank, "faction": "Не указана"}
        supabase.table("citizens").upsert(data).execute()
        await message.reply(f"📈 <b>{name}</b>, твои данные внесены в реестр Пакта!", parse_mode="HTML")
    except Exception as e: 
        logger.error(f"Ошибка регистрации: {e}")
        await message.reply("⚠️ Ошибка: База данных Пакта недоступна.")

@dp.message(Command("nation"))
async def cmd_nation(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return await message.reply("🧬 Укажите нацию: <code>/nation Татар</code>", parse_mode="HTML")
    
    u_id = str(message.from_user.id)
    nation = args[1][:20]
    try:
        supabase.table("citizens").update({"faction": nation}).eq("id", u_id).execute()
        await message.reply(f"🧬 Идентичность подтверждена: <b>{nation}</b>", parse_mode="HTML")
    except: await message.reply("❌ Сначала пройди регистрацию: /reg")

@dp.message(Command("passport"))
async def cmd_passport(message: types.Message):
    u_id = str(message.from_user.id)
    try:
        res = supabase.table("citizens").select("*").eq("id", u_id).execute()
        if not res.data: return await message.reply("⚠️ Личное дело отсутствует. Пройди /reg")
        
        u = res.data[0]
        date_reg = u.get('created_at', '2026-03-26')[:10]
        
        # Определяем статус верификации
        v_status = "🛡 ПОДТВЕРЖДЕНА" if u.get('verification', False) else "❌ НЕ ПОДТВЕРЖДЕНА"
        
        # Визуальный апгрейд досье (Связь -> ТЭГ)
        text = (
            f"🗄 <b>ЛИЧНОЕ ДОСЬЕ №{u['id'][-4:]}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>ИМЯ:</b> <code>{u['name']}</code>\n"
            f"🏛 <b>ГОСУДАРСТВО:</b> Пакт Волга-Урал\n"
            f"🧬 <b>НАЦИЯ:</b> {u['faction']}\n"
            f"🛡 <b>ПРОВЕРКА:</b> {v_status}\n"
            f"🎖 <b>СТАТУС:</b> {u['rank']}\n"
            f"📡 <b>ТЭГ:</b> {u['tag']}\n"
            f"📅 <b>ВЫДАНО:</b> {date_reg}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<i>Слава Пакту!</i>\n"
            f"{FLAGS}"
        )
        await message.reply(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка паспорта: {e}")
        await message.reply("📡 Сбой доступа к архивам.")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    try:
        res = supabase.table("citizens").select("*", count="exact").execute()
        total = res.count
        
        nations = {}
        for c in res.data:
            n = c.get('faction', 'Не указана')
            nations[n] = nations.get(n, 0) + 1
        
        n_list = "\n".join([f"├ {n}: <b>{count}</b>" for n, count in nations.items()])

        text = (
            f"📊 <b>ГОСУДАРСТВЕННАЯ СТАТИСТИКА</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👥 <b>ВСЕГО ГРАЖДАН:</b> {total}\n\n"
            f"🧬 <b>НАЦИОНАЛЬНЫЙ СОСТАВ:</b>\n"
            f"{n_list}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🏢 <b>АППАРАТ УПРАВЛЕНИЯ:</b>\n"
            f"└ Президент Пакта: <b>Трамадол</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{FLAGS}"
        )
        await message.reply(text, parse_mode="HTML")
    except: await message.reply("📊 Сводка недоступна.")

# --- ПРЕЗИДЕНТСКИЕ ПОЛНОМОЧИЯ ---

@dp.message(Command("set_rank"))
async def cmd_set_rank(message: types.Message):
    if str(message.from_user.id) != ADMIN_ID: return
    if not message.reply_to_message: return await message.reply("👤 Ответь на сообщение.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return await message.reply("❌ Укажи ранг: /set_rank Офицер")
    t_id = str(message.reply_to_message.from_user.id)
    try:
        supabase.table("citizens").update({"rank": args[1][:25]}).eq("id", t_id).execute()
        await message.reply(f"🎖 Гражданину присвоен статус: <b>{args[1]}</b>", parse_mode="HTML")
    except: pass

@dp.message(Command("verify"))
async def cmd_verify(message: types.Message):
    # Только Президент Трамадол может верифицировать
    if str(message.from_user.id) != ADMIN_ID:
        return await message.reply("⚠️ Доступ запрещён. Требуется печать Президента.")
    
    if not message.reply_to_message:
        return await message.reply("👤 Ответь на сообщение гражданина для верификации.")
    
    t_id = str(message.reply_to_message.from_user.id)
    t_name = message.reply_to_message.from_user.first_name
    
    try:
        # Пытаемся обновить колонку verification в базе
        # (Она должна быть типа boolean в Supabase)
        supabase.table("citizens").update({"verification": True}).eq("id", t_id).execute()
        
        text = (
            f"🛡 <b>ВЕРИФИКАЦИЯ ПАКТА</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Гражданин <b>{t_name}</b> прошёл личную проверку.\n"
            f"Профиль подтверждён Президентом Пакта.\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{FLAGS}"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка верификации: {e}")
        # Если колонки нет в базе, бот упадет сюда.
        await message.reply("📡 Сбой канцелярии. Проверь структуру базы в Supabase.")

# --- ИИ И НОВОСТИ ---

@dp.message(Command("news"))
async def cmd_news(message: types.Message):
    topic = message.text[5:].strip() or "Россия новости"
    wait = await message.answer("📡 Поиск в глобальной сети...")
    try:
        with DDGS() as ddgs:
            r = list(ddgs.text(f"{topic} 2026", region="ru-ru", max_results=3))
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
        name, rank = "Аноним", "Неизвестный"
        try:
            res = supabase.table("citizens").select("name, rank").eq("id", u_id).execute()
            if res.data: name, rank = res.data[0]['name'], res.data[0]['rank']
        except: pass
        
        ans = await ask_ai(f"{SYSTEM_CORE}\nПеред тобой {rank} {name}. Запрос: {message.text}")
        await message.answer(ans)

# --- ЗАПУСК ---

async def handle_root(request):
    return web.Response(text="Idel System v6.5 Online")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
