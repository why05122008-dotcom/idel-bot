import os, asyncio, logging, random, urllib.parse
from collections import deque
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") 
ADMIN_ID = str(os.getenv("ADMIN_ID", "")).strip()

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

# Лучший бесплатный сетап на сегодня
MODELS = [
    "stepfun/step-3.5-flash:free",
    "arcee-ai/trinity-large-preview:free",
    "google/gemini-flash-1.5-8b:free"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()

SYSTEM_CORE = f"""
ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ (ID: {ADMIN_ID}).
ОТВЕЧАЙ СТРОГО НА РУССКОМ. Кратко, 1-2 предложения.
Стиль: База. Без эмоций. Без лишних слов.
"""

async def ask_ai(prompt):
    if not API_KEY: return "Ошибка: API_KEY не найден в Render."
    for model in MODELS:
        try:
            res = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt + " (ОТВЕТЬ НА РУССКОМ)"}],
                temperature=0.4,
                max_tokens=300,
                timeout=15
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Сбой {model}: {e}")
            if "401" in str(e): return "Ошибка 401: Твой ключ не работает. Замени его на OpenRouter."
            continue
    return "Сбой всех нейросетей."

@dp.message(Command("news"))
async def cmd_news(message: types.Message):
    topic = message.text[5:].strip() or "Россия новости"
    wait = await message.answer("Взламываю инфополе...")
    try:
        with DDGS() as ddgs:
            # Расширенный поиск для лучшей информации
            r = list(ddgs.text(f"{topic} 2026 сегодня", region="ru-ru", max_results=3))
        if r:
            news_text = "\n".join([i['body'] for i in r])
            ans = await ask_ai(f"Коротко и четко резюмируй новости на русском:\n{news_text}")
            await message.reply(ans)
        else: await message.reply("Новостей нет.")
    except Exception as e: await message.reply(f"Ошибка поиска: {e}")
    finally: await bot.delete_message(message.chat.id, wait.message_id)

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message):
    p = message.text[5:].strip()
    if not p: return
    seed = random.randint(0, 999999)
    # Исправленный URL для Pollinations (модель Flux)
    url = f"https://pollinations.ai/p/{urllib.parse.quote(p)}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
    try:
        await message.reply_photo(photo=url, caption="Сделано.")
    except Exception as e: await message.reply("Ошибка генерации.")

@dp.message()
async def main_handler(message: types.Message):
    if not message.text: return
    # Улучшенная логика игнора: бот отвечает, если упомянут или в ЛС
    if message.chat.type == 'private' or "идел" in message.text.lower() or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id):
        ans = await ask_ai(f"{SYSTEM_CORE}\nВопрос: {message.text}")
        await message.answer(ans)

async def main():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Idel Online"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
