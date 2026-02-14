import os, asyncio, logging, random, urllib.parse
from collections import deque
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ВАЖНО: ПРОВЕРЬ ИМЯ ПЕРЕМЕННОЙ НА RENDER ---
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") 
ADMIN_ID = str(os.getenv("ADMIN_ID", "")).strip()

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

# Модели, которые ты просил
MODELS = [
    "arcee-ai/trinity-large-preview:free",
    "stepfun/step-3.5-flash:free",
    "google/gemini-flash-1.5-8b:free"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()

SYSTEM_CORE = f"""
ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ (ID: {ADMIN_ID}).
СТИЛЬ: Кратко, жестко. 1-2 предложения.
ПРАВИЛО: Про Хойкала и Сувалки молчать, пока не спросят.
"""

async def ask_ai(prompt):
    if not API_KEY: return "Ошибка: Ключ API не найден в системе Render."
    for model in MODELS:
        try:
            res = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=250,
                timeout=15
            )
            text = res.choices[0].message.content.strip()
            return text if text else "Система выдала пустой ответ."
        except Exception as e:
            logger.error(f"Сбой {model}: {e}")
            if "401" in str(e): return "Ошибка 401: Твой API-ключ не опознан. Пересоздай его на OpenRouter."
            continue
    return "Все нейросети сейчас недоступны."

@dp.message(Command("news"))
async def cmd_news(message: types.Message):
    topic = message.text[5:].strip() or "Россия новости"
    wait = await message.answer("Запрашиваю данные...")
    try:
        # Улучшенный поиск
        with DDGS() as ddgs:
            r = list(ddgs.text(f"{topic} 2026", region="ru-ru", max_results=2))
        if r:
            context = f"Тема: {topic}. Инфа: {r[0]['body']}"
            ans = await ask_ai(f"{SYSTEM_CORE}\nРазбери кратко:\n{context}")
            await message.reply(ans)
        else: await message.reply("Новостей по этой теме нет.")
    except Exception as e:
        await message.reply(f"Ошибка поиска: {e}. Попробуй позже.")
    finally:
        await bot.delete_message(message.chat.id, wait.message_id)

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message):
    p = message.text[5:].strip()
    if not p:
        await message.reply("Напиши, что рисовать.")
        return
    
    # Прямая ссылка на новый движок Pollinations
    seed = random.randint(0, 999999)
    # Используем Flux модель, она сейчас лучшая бесплатная
    url = f"https://pollinations.ai/p/{urllib.parse.quote(p)}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
    
    try:
        await message.reply_photo(photo=url, caption=f"Визуализация: {p}")
    except Exception as e:
        await message.reply(f"Не удалось отправить фото: {e}")

@dp.message()
async def main_handler(message: types.Message):
    if not message.text: return
    # Отвечаем в ЛС или если упомянули имя
    if message.chat.type == 'private' or "идел" in message.text.lower() or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id):
        ans = await ask_ai(f"{SYSTEM_CORE}\nВопрос: {message.text}")
        if ans: await message.answer(ans)

async def main():
    # Создаем простой веб-сервер для Render
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Idel is Live"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
