import os
import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import google.generativeai as genai
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Данные
TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

# Инициализация Google Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Пробуем разные варианты названий моделей для обхода ошибки 404
MODEL_NAMES = ['gemini-1.5-flash-latest', 'gemini-1.5-flash', 'gemini-pro']
model = None

for name in MODEL_NAMES:
    try:
        model = genai.GenerativeModel(name)
        logger.info(f"Выбрана модель: {name}")
        break
    except:
        continue

bot = Bot(token=TOKEN)
dp = Dispatcher()
memory = deque(maxlen=5)

BASE_PROMPT = (
    "Ты — Идел, циничный интеллектуал. "
    "Если тебе хамят — отвечай жестко. Если вежливы — будь холоден. "
    "К Трамадолу (Создателю) — с почтением. Мужской род, кратко."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, region='ru-ru', max_results=2)]
            return "\n".join([r['body'] for r in results])
    except:
        return ""

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Идел в строю. Зеркальные нейроны активны.")

@dp.message()
async def handle_message(message: types.Message):
    global memory
    if not message.text: return

    is_admin = str(message.from_user.id) == ADMIN_ID
    is_private = message.chat.type == 'private'
    is_mentioned = "идел" in message.text.lower()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot.id

    if not (is_private or is_mentioned or is_reply):
        if random.random() < 0.05: pass 
        else: return

    web_info = await search_web(message.text) if any(w in message.text.lower() for w in ['погода', 'новости']) else ""
    history = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    
    full_prompt = f"{BASE_PROMPT}\nИстория: {history}\nИнфо: {web_info}\nЮзер ({'АДМИН' if is_admin else 'Смертный'}): {message.text}"

    try:
        response = model.generate_content(full_prompt)
        answer = response.text
        
        if answer:
            # Реакция на агрессию в тексте
            if any(x in message.text.lower() for x in ['тупой', 'лох', 'херня']):
                await message.react([types.ReactionTypeEmoji(emoji="🌚")])
            
            await message.answer(answer)
            memory.append({"role": "user", "content": message.text})
            memory.append({"role": "assistant", "content": answer})
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        await message.answer("Система калибруется. Попробуй еще раз через 30 секунд.")

async def handle(request):
    return web.Response(text="Idel is Online")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    
    # Решение Conflict: сброс вебхука и пауза
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(10)
    
    await site.start()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
