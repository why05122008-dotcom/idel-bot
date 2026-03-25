import os, asyncio, logging, random, urllib.parse
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфиг
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "google/gemini-flash-1.5-8b:free"

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)
bot = Bot(token=TOKEN)
dp = Dispatcher()

SYSTEM_CORE = "ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ. Отвечай кратко, 1-2 sentences, на русском. Стиль: база."

async def ask_ai(prompt, is_news=False):
    if not API_KEY: return "Нет API ключа."
    system_text = SYSTEM_CORE + (" Сделай выжимку новостей одной фразой." if is_news else "")
    try:
        res = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system_text}, {"role": "user", "content": prompt}],
            temperature=0.5, max_tokens=300, timeout=20
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return "Нейросеть тупит."

@dp.message(Command("news"))
async def cmd_news(message: types.Message, command: CommandObject):
    topic = command.args or "новости"
    wait = await message.answer("🔍 Ищу...")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{topic} 2026", region="ru-ru", max_results=3))
        if results:
            ans = await ask_ai("\n".join([r['body'] for r in results]), is_news=True)
            await message.reply(ans)
        else: await message.reply("Ничего нет.")
    except: await message.reply("Ошибка поиска.")
    finally: await wait.delete()

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message, command: CommandObject):
    prompt = command.args
    if not prompt: return await message.reply("Напиши запрос.")
    url = f"https://pollinations.ai/p/{urllib.parse.quote(prompt)}?width=1024&height=1024&seed={random.randint(0, 999999)}&model=flux&nologo=true"
    try: await message.reply_photo(photo=url, caption=f"Запрос: {prompt}")
    except: await message.reply("Ошибка отрисовки.")

@dp.message(F.text)
async def main_handler(message: types.Message):
    txt = message.text.lower()
    if message.chat.type == 'private' or "идел" in txt or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id):
        ans = await ask_ai(txt.replace("идел", "").strip() or "Привет")
        await message.answer(ans)

# Веб-сервер для порта Render
async def handle_root(request):
    return web.Response(text="Idel OK")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Web server started on port {port}")

async def main():
    # Сначала запускаем веб-сервер, чтобы Render не убил процесс
    await start_webserver()
    
    # Затем запускаем бота
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot is starting polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
