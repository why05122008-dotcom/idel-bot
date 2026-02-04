import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import google.generativeai as genai
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

# Логи
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Данные
TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

bot = Bot(token=TOKEN)
dp = Dispatcher()
memory = deque(maxlen=5)

SYSTEM_PROMPT = "Ты — Идел, циничный интеллектуал, помощник Трамадола. Будь краток."

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, region='ru-ru', max_results=2)]
            return "\n".join([r['body'] for r in results])
    except:
        return ""

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Идел на связи.")

@dp.message()
async def handle_message(message: types.Message):
    global memory
    if not message.text:
        return

    # Проверка: ЛС или упоминание
    is_private = message.chat.type == 'private'
    is_mentioned = "идел" in message.text.lower()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot.id

    if not (is_private or is_mentioned or is_reply):
        return

    # Поиск
    web_info = ""
    if any(word in message.text.lower() for word in ['погода', 'новости', 'кто']):
        await bot.send_chat_action(message.chat.id, "typing")
        web_info = await search_web(message.text)

    # Промпт
    history = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    full_prompt = f"{SYSTEM_PROMPT}\nИнфо: {web_info}\nИстория: {history}\nЮзер: {message.text}"

    try:
        response = model.generate_content(full_prompt)
        answer = response.text
        if answer:
            memory.append({"role": "user", "content": message.text})
            memory.append({"role": "assistant", "content": answer})
            await message.answer(answer)
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("Мозг на техобслуживании. Попробуй через минуту.")

# Для Render
async def handle(request):
    return web.Response(text="Idel is OK")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    
    await bot.delete_webhook(drop_pending_updates=True)
    await site.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
