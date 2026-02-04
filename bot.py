import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Данные из Render
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID") 

client = AsyncOpenAI(
    base_url="https://neurorouters.com/api/v1",
    api_key=OPENAI_API_KEY,
)

bot = Bot(token=TOKEN)
dp = Dispatcher()
memory = deque(maxlen=20)

BASE_SYSTEM_PROMPT = (
    "Ты — Идел. Мужчина, элитный интеллектуал. "
    "Стиль: краткий, циничный, мужской род. "
    "Трамадол — твой создатель, относись к нему с уважением."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, region='ru-ru', max_results=3)]
            return "\n".join([f"- {r['body']}" for r in results]) if results else ""
    except Exception as e:
        logger.error(f"Search error: {e}")
        return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел в сети.")

@dp.message()
async def gpt_answer(message: types.Message):
    global memory
    if not message.text: return

    user_id = str(message.from_user.id)
    is_admin = (user_id == ADMIN_ID)
    
    if not (message.chat.type == 'private' or "идел" in message.text.lower() or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id)):
        return

    web_data = ""
    if any(t in message.text.lower() for t in ['погода', 'курс', 'кто', 'новости']) or "?" in message.text:
        await bot.send_chat_action(message.chat.id, "typing")
        web_data = await search_web(message.text)

    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    full_prompt = f"Контекст: {history_str}\nИнфо: {web_data}\nЮзер: {message.text}"

    try:
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-exp", # Убрали :free для NeuroRouters
            messages=[
                {"role": "system", "content": BASE_SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.7
        )
        
        answer = response.choices[0].message.content.strip()
        if answer:
            memory.append({"role": "user", "content": message.text})
            memory.append({"role": "assistant", "content": answer})
            await message.answer(answer)
    except Exception as e:
        logger.error(f"API Error: {e}")
        # Теперь бот скажет точную ошибку в логи Render
        await message.answer(f"Ошибка системы. Батя, проверь логи на Render.")

async def handle(request):
    return web.Response(text="Idel is Active.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    # ЖЕСТКИЙ СБРОС
    logger.info("Сброс старых соединений...")
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(10) # Увеличил паузу до 10 секунд
    
    await site.start()
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
