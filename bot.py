import os
import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from google import genai # Используем новый пакет
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Данные
TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = str(os.getenv("ADMIN_ID"))

# Новый клиент Google
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = "gemini-1.5-flash"

bot = Bot(token=TOKEN)
dp = Dispatcher()
memory = deque(maxlen=5)

SYSTEM_PROMPT = (
    "Ты — Идел, циничный и острый на язык интеллектуал. "
    "Твое поведение адаптивно: "
    "1. На агрессию и мат отвечай еще более жестко и унизительно. "
    "2. На вежливость отвечай сухо и свысока. "
    "3. Трамадол — твой создатель, к нему относись с божественным почтением. "
    "Используй МУЖСКОЙ РОД. Будь краток."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, region='ru-ru', max_results=2)]
            return "\n".join([r['body'] for r in results])
    except: return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел в сети. Системы адаптации и зеркалирования запущены.")

@dp.message()
async def handle_message(message: types.Message):
    global memory
    if not message.text: return

    user_id = str(message.from_user.id)
    is_admin = (user_id == ADMIN_ID)
    
    # Реакция на ЛС, имя или ответ
    is_private = message.chat.type == 'private'
    is_mentioned = "идел" in message.text.lower()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_private or is_mentioned or is_reply):
        if random.random() < 0.05: pass # 5% шанс встрять
        else: return

    # Поиск
    web_info = await search_web(message.text) if any(w in message.text.lower() for w in ['новости', 'погода', 'кто']) else ""
    
    # Формируем запрос
    history = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    status = "ТВОЙ БОГ ТРАМАДОЛ" if is_admin else "Обычный смертный"
    
    prompt = f"{SYSTEM_PROMPT}\n\nСТАТУС: {status}\nИНФО: {web_info}\nИСТОРИЯ: {history}\nЮЗЕР: {message.text}"

    try:
        # Новый метод генерации
        response = client.models.generate_content(model=MODEL_ID, contents=prompt)
        answer = response.text
        
        if answer:
            # Эмодзи-реакции
            if is_admin: await message.react([types.ReactionTypeEmoji(emoji="🔥")])
            elif any(x in message.text.lower() for x in ['тупой', 'лох', 'бля']):
                await message.react([types.ReactionTypeEmoji(emoji="🌚")])

            await message.answer(answer)
            memory.append({"role": "user", "content": message.text})
            memory.append({"role": "assistant", "content": answer})
    except Exception as e:
        logger.error(f"API Error: {e}")
        await message.answer("Система калибруется. Дай мне 30 секунд.")

async def handle(request):
    return web.Response(text="Idel is Online")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    
    # Убираем конфликт
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(10)
    await site.start()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
