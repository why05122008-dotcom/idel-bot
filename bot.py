import os, asyncio, logging, random, urllib.parse, io
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import AsyncDDGS

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") 
ADMIN_ID = str(os.getenv("ADMIN_ID", "ID_НЕ_УКАЗАН")).strip()

# Клиент OpenRouter
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

MODELS = [
    "stepfun/step-3.5-flash:free",
    "arcee-ai/trinity-large-preview:free",
    "google/gemini-flash-1.5-8b:free"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()

SYSTEM_CORE = f"ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ (ID: {ADMIN_ID}). ОТВЕЧАЙ СТРОГО НА РУССКОМ. Кратко, 1-2 предложения. Стиль: База. Без эмоций."

async def ask_ai(prompt):
    if not API_KEY: return "Ошибка: API_KEY не найден."
    for model in MODELS:
        try:
            res = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_CORE},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=300,
                timeout=20
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Сбой модели {model}: {e}")
            continue
    return "Сбой всех нейросетей. Попробуй позже."

@dp.message(Command("news"))
async def cmd_news(message: types.Message, command: CommandObject):
    topic = command.args or "Россия новости"
    wait = await message.answer("🔍 Взламываю инфополе...")
    
    try:
        async with AsyncDDGS() as ddgs:
            results = await ddgs.text(f"{topic} 2026 сегодня", region="ru-ru", max_results=3)
        
        if results:
            news_content = "\n".join([i['body'] for i in results])
            ans = await ask_ai(f"Сделай краткую выжимку новостей:\n{news_content}")
            await message.reply(ans)
        else:
            await message.reply("Новостей по этому запросу нет.")
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        await message.reply("Ошибка поиска. Попробуй другой запрос.")
    finally:
        await bot.delete_message(message.chat.id, wait.message_id)

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message, command: CommandObject):
    prompt = command.args
    if not prompt:
        return await message.reply("Напиши, что нарисовать. Пример: /draw киберпанк город")
    
    seed = random.randint(0, 999999)
    url = f"https://pollinations.ai/p/{urllib.parse.quote(prompt)}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
    
    try:
        # Скачиваем картинку заранее, чтобы не было ошибки таймаута от Telegram
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    photo = types.BufferedInputFile(data, filename="draw.jpg")
                    await message.reply_photo(photo=photo, caption="Сделано.")
                else:
                    await message.reply("Сервис генерации временно недоступен.")
    except Exception as e:
        logger.error(f"Ошибка отрисовки: {e}")
        await message.reply("Ошибка при создании изображения.")

@dp.message(F.text)
async def main_handler(message: types.Message):
    # Условие: ЛС, упоминание имени или ответ на сообщение бота
    is_private = message.chat.type == 'private'
    is_mentioned = "идел" in message.text.lower()
    is_reply_to_me = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if is_private or is_mentioned or is_reply_to_me:
        # Убираем имя бота из текста, чтобы ИИ не путался
        clean_text = message.text.lower().replace("идел", "").strip()
        ans = await ask_ai(clean_text or "Привет")
        await message.answer(ans)

async def handle_root(request):
    return web.Response(text="Idel Online 2026")

async def main():
    # Настройка веб-сервера для Render (Keep-alive)
    app = web.Application()
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    
    await site.start()
    await bot.delete_webhook(drop_pending_updates=True)
    
    logger.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
