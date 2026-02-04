import os
import asyncio
import logging
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфиги из Render
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") 
ADMIN_ID = str(os.getenv("ADMIN_ID"))

# Ограничение одновременных запросов (чтобы не забанили API)
semaphore = asyncio.Semaphore(5) 

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

# Актуальный список моделей
MODELS = [
    "arcee-ai/trinity-large-preview:free",
    "tngtech/deepseek-r1t2-chimera:free",
    "google/gemini-2.0-flash-thinking-exp:free"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Память: для каждого юзера свой контекст
user_memories = {}

# Жесткий промпт Идела
SYSTEM_PROMPT = (
    "Ты — Идел, бескомпромиссный, циничный помощник Трамадола. "
    "1. Отвечай КОРОТКО и ЕДКО. Никакой воды и пафоса про ИИ. "
    "2. Трамадол (ADMIN) — твой создатель, к нему только лаконичное уважение. "
    "3. Остальные юзеры (MINION) — ничтожества. "
    "4. Если вопрос тупой или пошлый — ответь максимально кратко и унизительно. "
    "Используй МУЖСКОЙ РОД. Не повторяйся."
)

async def deep_search(query):
    try:
        with DDGS() as ddgs:
            results = [r['body'] for r in ddgs.text(query, region='ru-ru', max_results=2)]
            return "\n".join(results)
    except: return ""

# --- ФОНОВАЯ ГЕНЕРАЦИЯ КАРТИНОК ---
async def process_draw(message: types.Message, prompt: str):
    async with semaphore:
        try:
            # Перевод промпта без лишней болтовни
            res = await client.chat.completions.create(
                model=MODELS[0],
                messages=[{"role": "system", "content": "Translate to English. Only prompt text."},
                          {"role": "user", "content": prompt}],
                temperature=0.1
            )
            en_prompt = res.choices[0].message.content.strip()
            image_url = f"https://image.pollinations.ai/prompt/{en_prompt}?width=1024&height=1024&model=flux"
            
            await bot.send_photo(message.chat.id, photo=image_url, caption="Твой бред визуализирован.")
        except Exception as e:
            logger.error(f"Draw error: {e}")
            await message.answer("Художник в коме. Позже.")

# --- ФОНОВАЯ ОБРАБОТКА ТЕКСТА ---
async def process_text(message: types.Message):
    async with semaphore:
        user_id = str(message.from_user.id)
        is_admin = (user_id == ADMIN_ID)
        
        if user_id not in user_memories:
            user_memories[user_id] = deque(maxlen=4)

        # Веб-поиск для точности
        web_context = ""
        if any(x in message.text.lower() for x in ['кто', 'что', 'найди', 'новости', 'факт']):
            web_context = await deep_search(message.text)

        history = "\n".join([f"{m['role']}: {m['content']}" for m in user_memories[user_id]])
        status = "BOSS" if is_admin else "MINION"

        for model_id in MODELS:
            try:
                response = await client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": f"{SYSTEM_PROMPT}\nИНФО: {web_context}\nЮЗЕР: {status}"},
                        {"role": "user", "content": f"ИСТОРИЯ: {history}\nВвод: {message.text}"}
                    ],
                    temperature=0.5,
                    timeout=30
                )
                answer = response.choices[0].message.content.strip()
                if answer:
                    await message.answer(answer)
                    user_memories[user_id].append({"role": "user", "content": message.text})
                    user_memories[user_id].append({"role": "assistant", "content": answer})
                    return
            except Exception as e:
                logger.warning(f"Сбой модели {model_id}: {e}")
                continue
        await message.answer("Перегрузка. Свали в туман.")

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message):
    prompt = message.text.replace("/draw", "").strip()
    if not prompt:
        await message.answer("Что рисовать, Смертный?")
        return
    asyncio.create_task(process_draw(message, prompt))

@dp.message()
async def handle_all(message: types.Message):
    if not message.text: return
    
    # Фильтр: ЛС, упоминание или ответ на сообщение бота
    is_private = message.chat.type == 'private'
    is_mentioned = "идел" in message.text.lower()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if is_private or is_mentioned or is_reply:
        asyncio.create_task(process_text(message))

# Веб-сервер для Render
async def handle_web(request): return web.Response(text="Idel Hyper-Engine Online")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_web)
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    
    await bot.delete_webhook(drop_pending_updates=True)
    await site.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
