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

# Логи
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Данные из Render
TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

bot = Bot(token=TOKEN)
dp = Dispatcher()
memory = deque(maxlen=5)

# Улучшенная личность с адаптивным поведением
BASE_PROMPT = (
    "Ты — Идел, циничный интеллектуал и правая рука Трамадола. "
    "Твое поведение адаптивно: "
    "1. Если юзер проявляет агрессию, хамит или тупит — отвечай максимально жестко, едко и высокомерно. "
    "2. Если юзер вежлив или нейтрален — отвечай спокойно, кратко и по делу, но сохраняй холодную дистанцию. "
    "3. К Трамадолу (Создателю) всегда относись с абсолютным почтением. "
    "Используй исключительно МУЖСКОЙ РОД. Будь лаконичен."
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
    await message.answer("Идел на связи. Системы адаптации активны.")

@dp.message()
async def handle_message(message: types.Message):
    global memory
    if not message.text:
        return

    is_admin = str(message.from_user.id) == ADMIN_ID
    is_private = message.chat.type == 'private'
    is_mentioned = "идел" in message.text.lower()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot.id

    # Шанс 5% встрять в разговор без упоминания, если в чате весело
    if not (is_private or is_mentioned or is_reply):
        if random.random() < 0.05: pass 
        else: return

    # Поиск инфы
    web_info = ""
    if any(word in message.text.lower() for word in ['погода', 'новости', 'кто']):
        await bot.send_chat_action(message.chat.id, "typing")
        web_info = await search_web(message.text)

    # Формируем запрос с учетом тона
    history = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    status = "ТРАМАДОЛ (БОГ)" if is_admin else "Обычный смертный"
    
    full_prompt = (
        f"{BASE_PROMPT}\n"
        f"СТАТУС СОБЕСЕДНИКА: {status}\n"
        f"ИНФО ИЗ СЕТИ: {web_info}\n"
        f"КОНТЕКСТ ЧАТА: {history}\n"
        f"СООБЩЕНИЕ ЮЗЕРА: {message.text}\n"
        "ЗАДАНИЕ: Проанализируй тон юзера и ответь соответственно его энергии."
    )

    try:
        response = model.generate_content(full_prompt)
        answer = response.text
        
        if answer:
            # Авто-реакции для стиля
            if any(bad in message.text.lower() for bad in ['тупой', 'лох', 'херня']):
                await message.react([types.ReactionTypeEmoji(emoji="🌚")])
            elif is_admin:
                await message.react([types.ReactionTypeEmoji(emoji="🔥")])

            memory.append({"role": "user", "content": message.text})
            memory.append({"role": "assistant", "content": answer})
            await message.answer(answer)
            
    except Exception as e:
        logger.error(f"Error: {e}")
        if "429" in str(e):
            await message.answer("Остынь. Слишком много слов.")

# Сервер для Render
async def handle(request):
    return web.Response(text="Idel is Mirroring...")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    
    # Решение ошибки Conflict (пауза 10 сек)
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(10)
    
    await site.start()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
