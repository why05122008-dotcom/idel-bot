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

# Самые стабильные модели на сегодня
MODELS = [
    "stepfun/step-3.5-flash:free",
    "google/gemini-flash-1.5-8b:free",
    "arcee-ai/trinity-large-preview:free"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ЖЕСТКИЙ СИСТЕМНЫЙ ПРОМПТ (Запрет на иностранные языки)
SYSTEM_CORE = f"""
ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ.
ОТВЕЧАЙ СТРОГО НА РУССКОМ ЯЗЫКЕ.
Стиль: Кратко, база, без пафоса.
Про Хойкала и Сувалки молчи, пока не спросят.
"""

async def ask_ai(prompt):
    for model in MODELS:
        try:
            res = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt + " (ОТВЕТЬ НА РУССКОМ)"}],
                temperature=0.3,
                max_tokens=250,
                timeout=15
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Сбой {model}: {e}")
            continue
    return "Ошибка связи с ядром."

@dp.message(Command("news"))
async def cmd_news(message: types.Message):
    topic = message.text[5:].strip() or "Россия новости"
    wait = await message.answer("Сводка новостей...")
    try:
        with DDGS() as ddgs:
            # Поиск только на русском
            r = list(ddgs.text(f"{topic} сегодня", region="ru-ru", max_results=2))
        if r:
            ans = await ask_ai(f"Сделай краткую выжимку новостей на РУССКОМ: {r[0]['body']}")
            await message.reply(ans)
        else: await message.reply("Новостей не найдено.")
    except Exception as e: await message.reply(f"Ошибка поиска: {e}")
    finally: await bot.delete_message(message.chat.id, wait.message_id)

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message):
    p = message.text[5:].strip()
    if not p: return
    
    # Новый движок Flux (Нано Банана аналоги отдыхают)
    seed = random.randint(0, 999999)
    safe_prompt = urllib.parse.quote(p)
    # Используем обновленный стабильный URL
    url = f"https://pollinations.ai/p/{safe_prompt}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
    
    try:
        await message.reply_photo(photo=url, caption=f"Визуализация: {p}")
    except Exception as e:
        await message.reply("Сбой отрисовки.")

@dp.message()
async def main_handler(message: types.Message):
    if not message.text: return
    if message.chat.type == 'private' or "идел" in message.text.lower() or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id):
        ans = await ask_ai(f"{SYSTEM_CORE}\nВопрос: {message.text}")
        await message.answer(ans)

async def main():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Idel Core Active"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
