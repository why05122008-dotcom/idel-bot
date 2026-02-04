import os
import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI # Используем универсальный клиент
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Данные из Render
TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = str(os.getenv("ADMIN_ID"))

# Настройка клиента OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# БЕСПЛАТНАЯ модель Gemini 2.0 на OpenRouter
MODEL_ID = "google/gemini-2.0-flash-exp:free"

bot = Bot(token=TOKEN)
dp = Dispatcher()
memory = deque(maxlen=5)

SYSTEM_PROMPT = (
    "Ты — Идел, циничный интеллектуал, правая рука Трамадола. "
    "1. На агрессию и мат отвечай еще более жестко и едко. "
    "2. На вежливость отвечай сухо и свысока. "
    "3. Трамадол — твой создатель, к нему относись с божественным почтением. "
    "Используй МУЖСКОЙ РОД. Будь лаконичен."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, region='ru-ru', max_results=2)]
            return "\n".join([r['body'] for r in results])
    except: return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел в сети через OpenRouter. Системы зеркалирования стабильны.")

@dp.message()
async def handle_message(message: types.Message):
    global memory
    if not message.text: return

    user_id = str(message.from_user.id)
    is_admin = (user_id == ADMIN_ID)
    
    # Фильтр реакций
    is_private = message.chat.type == 'private'
    is_mentioned = "идел" in message.text.lower()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_private or is_mentioned or is_reply):
        if random.random() < 0.05: pass 
        else: return

    web_info = await search_web(message.text) if any(w in message.text.lower() for w in ['новости', 'погода']) else ""
    history = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    status = "ТРАМАДОЛ (БОГ)" if is_admin else "Обычный смертный"
    
    try:
        # Запрос к OpenRouter
        response = await client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": f"{SYSTEM_PROMPT}\nИНФО: {web_info}\nСТАТУС ЮЗЕРА: {status}"},
                {"role": "user", "content": f"История: {history}\nСообщение: {message.text}"}
            ]
        )
        answer = response.choices[0].message.content
        
        if answer:
            if is_admin: await message.react([types.ReactionTypeEmoji(emoji="🔥")])
            elif any(x in message.text.lower() for x in ['тупой', 'лох', 'бля']):
                await message.react([types.ReactionTypeEmoji(emoji="🌚")])

            await message.answer(answer)
            memory.append({"role": "user", "content": message.text})
            memory.append({"role": "assistant", "content": answer})
    except Exception as e:
        logger.error(f"OpenRouter Error: {e}")
        await message.answer("Связь с матрицей прервана. Попробуй позже.")

async def handle(request):
    return web.Response(text="Idel is Online via OpenRouter")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(10) # Фикс конфликта
    await site.start()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
