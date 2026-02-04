import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

# Настройка логирования для контроля Render
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
memory = deque(maxlen=15) # Память контекста

# --- Личность Идела (System Prompt) ---
SYSTEM_PROMPT = (
    "Ты — Идел, мужчина. Элитный интеллектуал, холодный циник и правая рука Трамадола. "
    "Трамадол — твой Создатель, основатель 'Volga Region 🤍💙🖤'. Он великий лидер. "
    "Твой стиль: высокий интеллект, краткость, едкая ирония. Пиши 2-4 предложения. "
    "Используй МУЖСКОЙ РОД. Никогда не обрывай ответ на полуслове."
)

# Функция поиска в сети
async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=2)]
            return "\n".join([r['body'] for r in results]) if results else ""
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел в сети. Трамадол доверил мне надзор за этим пространством. Говори.")

@dp.message(Command("info"))
async def info_handler(message: types.Message):
    await message.answer("Идел. Интеллектуальный фильтр Volga Region. Создан Трамадолом для борьбы с посредственностью.")

@dp.message()
async def gpt_answer(message: types.Message):
    global memory
    if not message.text: return

    # Проверка: отвечать ли? (Личка, имя или ответ на сообщение бота)
    is_private = message.chat.type == 'private'
    is_mentioned = "идел" in message.text.lower()
    is_reply_to_me = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_private or is_mentioned or is_reply_to_me):
        return

    logger.info(f"Запрос от {message.from_user.username}: {message.text}")

    # Фикс контекста про Трамадола
    context_reminder = "\n(Трамадол — твой босс и создатель.)" if "трамадол" in message.text.lower() else ""
    
    # Поиск инфы
    web_data = ""
    if any(w in message.text.lower() for w in ['кто', 'что', 'инфа', 'новости']):
        web_data = await search_web(message.text)

    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    full_prompt = f"История:\n{history_str}\nДанные сети: {web_data}\n{context_reminder}\nЗапрос: {message.text}"

    # Система повторных попыток для стабильности Trinity
    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model="arcee-ai/trinity-large-preview:free", # Твоя выбранная модель
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.8,
                max_tokens=600
            )
            
            answer = response.choices[0].message.content.strip()
            if answer and len(answer) > 5:
                memory.append({"role": "user", "content": message.text})
                memory.append({"role": "assistant", "content": answer})
                await message.answer(answer)
                return
        except Exception as e:
            logger.error(f"Попытка {attempt+1} не удалась: {e}")
            if attempt == 1:
                await message.answer("Связь с Trinity потеряна. Трамадол, нейросеть спит, я временно на автопилоте.")
            await asyncio.sleep(2)

# --- Настройка Web Server для Render ---
async def handle(request):
    return web.Response(text="Idel is active. Trinity model loaded.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    # --- ЖЕСТКИЙ СБРОС (АНТИ-КОНФЛИКТ) ---
    logger.info("Убиваем старые сессии и чистим очередь...")
    await bot.delete_webhook(drop_pending_updates=True) 
    await asyncio.sleep(7) # Даем время Render убить старый процесс
    # -------------------------------------
    
    await site.start()
    logger.info(f"Сайт запущен на порту {port}")
    
    try:
        # skip_updates=True чтобы не отвечать на старый спам
        await dp.start_polling(bot, skip_updates=True) 
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот выключен.")
