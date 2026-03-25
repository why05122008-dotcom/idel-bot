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

# Клиент OpenRouter (оставил одну проверенную модель)
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)
MODEL = "google/gemini-flash-1.5-8b:free"

bot = Bot(token=TOKEN)
dp = Dispatcher()

SYSTEM_CORE = "ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ. Отвечай кратко, 1-2 предложения, на русском. Стиль: база, без эмоций."

async def ask_ai(prompt, is_news=False):
    if not API_KEY: return "Ошибка: API_KEY не найден."
    
    system_text = SYSTEM_CORE
    if is_news:
        system_text += " Тебе даны новости. Сделай из них краткую выжимку одной фразой."

    try:
        res = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=300,
            timeout=20
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Ошибка ИИ: {e}")
        return "Нейросеть временно недоступна."

@dp.message(Command("news"))
async def cmd_news(message: types.Message, command: CommandObject):
    topic = command.args or "Россия новости"
    wait = await message.answer("🔍 Ищу инфу...")
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{topic} 2026", region="ru-ru", max_results=3))
        
        if results:
            news_blob = "\n".join([r['body'] for r in results])
            ans = await ask_ai(news_blob, is_news=True)
            await message.reply(ans)
        else:
            await message.reply("Ничего не нашел.")
    except Exception as e:
        logger.error(f"Search error: {e}")
        await message.reply("Ошибка поиска.")
    finally:
        await wait.delete()

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message, command: CommandObject):
    prompt = command.args
    if not prompt:
        return await message.reply("Напиши запрос, например: /draw космос")
    
    seed = random.randint(0, 999999)
    encoded_prompt = urllib.parse.quote(prompt)
    # Используем прямую ссылку, чтобы не грузить сервер Render
    url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
    
    try:
        await message.reply_photo(photo=url, caption=f"Запрос: {prompt}")
    except Exception as e:
        logger.error(f"Draw error: {e}")
        await message.reply("Не удалось загрузить картинку.")

@dp.message(F.text)
async def main_handler(message: types.Message):
    txt = message.text.lower()
    is_private = message.chat.type == 'private'
    is_mentioned = "идел" in txt
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if is_private or is_mentioned or is_reply:
        clean_text = txt.replace("идел", "").strip() or "Привет"
        ans = await ask_ai(clean_text)
        await message.answer(ans)

async def handle_root(request):
    return web.Response(text="Idel Online")

async def main():
    # Веб-сервер для Render
    app = web.Application()
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 
