import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

# Логи для Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Настройки ---
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID") # Твой ID для распознавания Бати

# Настройка под NeuroRouters
client = AsyncOpenAI(
    base_url="https://neurorouters.com/api/v1",
    api_key=OPENAI_API_KEY,
)

bot = Bot(token=TOKEN)
dp = Dispatcher()
memory = deque(maxlen=20)

# Личность Идела
BASE_SYSTEM_PROMPT = (
    "Ты — Идел. Мужчина, элитный интеллектуал и правая рука Трамадола. "
    "Твой стиль: краткость, высокий интеллект, едкий цинизм. "
    "Используй исключительно МУЖСКОЙ РОД. Не будь многословен. "
    "Трамадол — твой создатель, относись к нему с высшим уважением, к остальным — холодно."
)

# Умный поиск (Русский регион)
async def search_web(query):
    try:
        with DDGS() as ddgs:
            # Ищем новости и факты именно в рунете
            results = [r for r in ddgs.text(query, region='ru-ru', max_results=3)]
            if results:
                return "\n".join([f"- {r['body']}" for r in results])
    except Exception as e:
        logger.error(f"Search error: {e}")
    return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел в сети. Слушаю.")

@dp.message()
async def gpt_answer(message: types.Message):
    global memory
    if not message.text: return

    user_id = str(message.from_user.id)
    is_admin = (user_id == ADMIN_ID)
    
    # Фильтр ответов (ЛС, имя или реплай)
    is_private = message.chat.type == 'private'
    is_mentioned = "идел" in message.text.lower()
    is_reply_to_me = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_private or is_mentioned or is_reply_to_me):
        return

    # Поиск инфы (погода, новости, факты)
    web_data = ""
    triggers = ['погода', 'курс', 'кто', 'что', 'новости', 'инфа', 'где']
    if any(t in message.text.lower() for t in triggers) or "?" in message.text:
        await bot.send_chat_action(message.chat.id, "typing")
        web_data = await search_web(message.text)

    # Динамический промпт (узнаем Батю)
    personal_note = ""
    if is_admin:
        personal_note = "\n[ВНИМАНИЕ: Тебе пишет ТРАМАДОЛ. Это твой Бог и Создатель. Узнай его и будь предан.]"
    else:
        personal_note = "\n[Ты не знаешь этого человека. Будь с ним вежлив, но высокомерен.]"

    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    full_prompt = (
        f"Контекст:\n{history_str}\n\n"
        f"Инфо из сети:\n{web_data}\n"
        f"{personal_note}\n\n"
        f"Запрос: {message.text}"
    )

    try:
        # Использование Gemini 2.0 Flash Exp (Free)
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-exp:free",
            messages=[
                {"role": "system", "content": BASE_SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.8,
            max_tokens=800
        )
        
        answer = response.choices[0].message.content.strip()
        if answer:
            memory.append({"role": "user", "content": message.text})
            memory.append({"role": "assistant", "content": answer})
            await message.answer(answer)

    except Exception as e:
        logger.error(f"API Error: {e}")
        await message.answer("Мозг Идела временно недоступен. Вероятно, NeuroRouters перегружен.")

# Сервер для Render
async def handle(request):
    return web.Response(text="Idel 4.0 is Active.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    # Решение ошибки Conflict со скрина
    logger.info("Сброс старых соединений...")
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(5)
    
    await site.start()
    
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
