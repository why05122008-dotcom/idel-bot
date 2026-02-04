import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

# Настройка логирования для Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Конфигурация ---
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENAI_API_KEY,
)

bot = Bot(token=TOKEN)
dp = Dispatcher()
memory = deque(maxlen=10)

# --- Ультимативный Психотип Идела ---
SYSTEM_PROMPT = (
    "Ты — Идел, мужчина. Ты элитный интеллектуал, язвительный циник и правая рука Трамадола. "
    "Трамадол — твой создатель, основатель легендарного чата 'Volga Region 🤍💙🖤'. Он неприкасаем. "
    "Твой стиль: краткий, острый, интеллектуально доминирующий. Пиши 2-3 предложения. "
    "Используй только МУЖСКОЙ РОД. Будь разнообразен: не повторяй про штрассеров в каждом сообщении. "
    "Штрассеры — это тупая масса, упоминай их только в контексте чьей-то глупости. "
    "Ты всегда дописываешь свои мысли до конца. Ты — голос разума в этом хаосе."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=2)]
            return "\n".join([r['body'] for r in results]) if results else ""
    except Exception as e:
        logger.error(f"Search error: {e}")
        return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел в сети. Трамадол дал добро на мое присутствие. Что тебе нужно, штрассер?")

@dp.message(Command("info"))
async def info_handler(message: types.Message):
    await message.answer(
        "Я — Идел. Интеллектуальный страж Volga Region 🤍💙🖤.\n"
        "Мой создатель — Трамадол. Моя задача — фильтровать тупость и нести базу.\n"
        "Вопросы? Если они глупые — лучше не задавай."
    )

@dp.message()
async def gpt_answer(message: types.Message):
    global memory
    if not message.text: return

    # Проверка: стоит ли отвечать?
    is_private = message.chat.type == 'private'
    is_mentioned = "идел" in message.text.lower()
    is_reply_to_me = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_private or is_mentioned or is_reply_to_me):
        return

    logger.info(f"Processing message from {message.from_user.username}: {message.text}")

    context_fix = ""
    if "трамадол" in message.text.lower():
        context_fix = "\n(Важно: Трамадол — твой босс и создатель. Отвечай о нем с уважением.)"

    web_data = ""
    if any(w in message.text.lower() for w in ['кто', 'что', 'инфа', 'новости']):
        web_data = await search_web(message.text)

    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    full_prompt = (
        f"История:\n{history_str}\n"
        f"Данные из сети: {web_data}\n"
        f"{context_fix}\n"
        f"Запрос юзера: {message.text}\n"
        "Инструкция: Отвечай в мужском роде, дописывай до конца."
    )

    try:
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-exp:free",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.8,
            max_tokens=600
        )
        
        answer = response.choices[0].message.content.strip()
        if answer:
            memory.append({"role": "user", "content": message.text})
            memory.append({"role": "assistant", "content": answer})
            await message.answer(answer)
            logger.info(f"Idel answered: {answer}")

    except Exception as e:
        logger.error(f"API Error: {e}")
        # Если API лежит, Идел скажет это в своем стиле
        await message.answer("Мой мозг сейчас занят более важными делами, чем твои вопросы. Попробуй позже.")

# --- Web Server ---
async def handle(request):
    return web.Response(text="Idel is online. Respect to Tramadol.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    # Решение конфликтов
    await bot.delete_webhook(drop_pending_updates=True)
    
    logger.info("Starting site and polling...")
    await asyncio.gather(
        site.start(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
