import os, asyncio, logging, random, urllib.parse
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Данные
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") 
ADMIN_ID = str(os.getenv("ADMIN_ID", "8464693849")).strip()

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

MODELS = [
    "arcee-ai/trinity-large-preview:free",
    "stepfun/step-3.5-flash:free",
    "google/gemini-flash-1.5-8b:free"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()

SYSTEM_CORE = """
ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ.
ОТВЕЧАЙ СТРОГО НА РУССКОМ. Кратко, по делу.
Сегодня 26 марта 2026 года.
"""

async def ask_ai(prompt, system=SYSTEM_CORE):
    for model in MODELS:
        try:
            res = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=400,
                timeout=20
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Сбой {model}: {e}")
            continue
    return "Ядро временно недоступно."

async def translate_to_en(text):
    # Вспомогательная функция для /draw
    prompt = f"Translate the following prompt for image generation to English. Output ONLY the translation: {text}"
    return await ask_ai(prompt, system="You are a professional translator to English.")

@dp.message(Command("news"))
async def cmd_news(message: types.Message):
    topic = message.text[5:].strip() or "Россия последние события"
    wait = await message.answer("🔎 Вскрываю свежие сводки...")
    try:
        with DDGS() as ddgs:
            # timelimit='d' — ВАЖНО: фильтр только за последние сутки
            r = list(ddgs.text(f"{topic}", region="ru-ru", timelimit='d', max_results=5))
        
        if r:
            context = "\n\n".join([f"Источник: {i['title']}\nСуть: {i['body']}" for i in r])
            prompt = f"На основе данных ниже составь краткую базу новостей по теме '{topic}' за сегодня (26.03.2026). Игнорируй старые даты:\n\n{context}"
            ans = await ask_ai(prompt)
            await message.reply(f"📰 **База по теме: {topic}**\n\n{ans}")
        else:
            await message.reply("За последние 24 часа новостей не найдено.")
    except Exception as e:
        await message.reply(f"Ошибка поиска: {e}")
    finally:
        await bot.delete_message(message.chat.id, wait.message_id)

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message):
    p = message.text[5:].strip()
    if not p:
        return await message.reply("Напиши, что нарисовать.")
    
    wait = await message.answer("🎨 Подготавливаю холст...")
    
    # Переводим на английский, чтобы избежать заглушек и улучшить качество
    eng_p = await translate_to_en(p)
    seed = random.randint(0, 999999)
    
    # Используем прямую ссылку с параметром nologo
    url = f"https://pollinations.ai/p/{urllib.parse.quote(eng_p)}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
    
    try:
        await message.reply_photo(photo=url, caption=f"✨ Визуализация: {p}")
    except Exception as e:
        await message.reply("Генератор занят или запрос заблокирован.")
    finally:
        await bot.delete_message(message.chat.id, wait.message_id)

@dp.message()
async def main_handler(message: types.Message):
    if not message.text: return
    # Реакция на имя или ЛС
    if message.chat.type == 'private' or "идел" in message.text.lower() or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id):
        ans = await ask_ai(message.text)
        await message.answer(ans)

async def main():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Idel Online"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
