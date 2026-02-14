import os, asyncio, logging, random, urllib.parse
from collections import deque
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ГОРЯЧАЯ ЗАМЕНА ПЕРЕМЕННЫХ ---
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") # Убедись, что на Render ключ вставлен без пробелов!
ADMIN_ID = str(os.getenv("ADMIN_ID", "")).strip()

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

# БЕСПЛАТНЫЕ И БЫСТРЫЕ АНАЛОГИ (Nano-уровень)
MODELS = [
    "meta-llama/llama-3.2-1b-instruct:free", # Та самая "нано" скорость
    "google/gemini-flash-1.5-8b:free", 
    "mistralai/mistral-7b-instruct:free"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ЖЕСТКАЯ ИНСТРУКЦИЯ (Ничего лишнего)
SYSTEM_CORE = f"""
ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ (ID: {ADMIN_ID}).
СТИЛЬ: Максимально кратко. 1-2 предложения. Без пафоса. Без скобок.
ПРАВИЛО: ПРО ХОЙКАЛА И СУВАЛКИ МОЛЧАТЬ. Упоминать их ТОЛЬКО если пользователь спросил про них первым.
ПОЗИЦИЯ: РФ — сила.
"""

async def ask_ai(prompt):
    for model in MODELS:
        try:
            res = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3, # Минимум фантазии
                max_tokens=150,
                timeout=12
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            if "401" in str(e): return "Ошибка: API Ключ не принят OpenRouter (401). Перепроверь его в Render."
            continue
    return "Сбой систем."

@dp.message(Command("news"))
async def cmd_news(message: types.Message):
    topic = message.text[5:].strip() or "Россия"
    try:
        with DDGS() as ddgs:
            r = list(ddgs.text(f"{topic} новости сегодня", region="ru-ru", max_results=2))
        if r:
            txt = "\n".join([i['body'] for i in r])
            ans = await ask_ai(f"{SYSTEM_CORE}\nСуть новостей кратко:\n{txt}")
            await message.reply(ans)
        else: await message.reply("Новостей нет.")
    except Exception as e: await message.reply(f"Ошибка поиска: {e}")

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message):
    p = message.text[5:].strip()
    if not p: return
    # Прямая генерация без лишних слов
    seed = random.randint(0, 99999)
    url = f"https://pollinations.ai/p/{urllib.parse.quote(p)}?width=1024&height=1024&seed={seed}&nologo=true"
    await message.reply_photo(photo=url, caption="Готово.")

async def process_text(message: types.Message):
    is_admin = str(message.from_user.id) == ADMIN_ID
    prefix = f"{random.choice(['Господин', 'Повелитель'])}, " if is_admin else ""
    ans = await ask_ai(f"{SYSTEM_CORE}\nВопрос: {message.text}")
    await message.answer(f"{prefix}{ans}")

@dp.message()
async def main_handler(message: types.Message):
    if not message.text: return
    if message.chat.type == 'private' or "идел" in message.text.lower() or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id):
        asyncio.create_task(process_text(message))

async def main():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Idel Core Active"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
