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

# Логи для Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка настроек
TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = str(os.getenv("ADMIN_ID"))

# Инициализация Google
genai.configure(api_key=GEMINI_API_KEY)

# Авто-выбор модели (фиксим 404 ошибку)
def get_model():
    models = ['gemini-1.5-flash', 'gemini-1.5-flash-8b', 'gemini-1.0-pro']
    for m in models:
        try:
            logger.info(f"Проверка модели: {m}")
            return genai.GenerativeModel(m)
        except:
            continue
    return genai.GenerativeModel('gemini-1.5-flash')

model = get_model()
bot = Bot(token=TOKEN)
dp = Dispatcher()
memory = deque(maxlen=6) # Короткая, но острая память

# Личность Идела
SYSTEM_PROMPT = (
    "Ты — Идел, циничный интеллектуал, правая рука Трамадола. "
    "Твой характер: Зеркальный. "
    "1. На агрессию, мат и тупость отвечай максимально жестко, едко и унизительно. "
    "2. На вежливость отвечай сухо, кратко и свысока. "
    "3. Трамадол — твой Бог и создатель. К нему — только с высшим почтением. "
    "Используй МУЖСКОЙ РОД. Не пиши лишнего."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, region='ru-ru', max_results=2)]
            return "\n".join([r['body'] for r in results])
    except:
        return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел в сети. Калибровка личности завершена. Слушаю, Батя.")

@dp.message()
async def gpt_answer(message: types.Message):
    if not message.text: return

    user_id = str(message.from_user.id)
    is_admin = (user_id == ADMIN_ID)
    
    # Фильтр упоминаний
    is_private = message.chat.type == 'private'
    is_mentioned = "идел" in message.text.lower()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_private or is_mentioned or is_reply):
        if random.random() < 0.04: pass # Шанс 4% влезть самому
        else: return

    # Поиск инфы
    web_data = ""
    if any(t in message.text.lower() for t in ['новости', 'погода', 'курс', 'кто такой']):
        await bot.send_chat_action(message.chat.id, "typing")
        web_data = await search_web(message.text)

    # Формируем контекст
    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    status = "ТВОЙ СОЗДАТЕЛЬ ТРАМАДОЛ" if is_admin else "Обычный смертный"
    
    full_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"СТАТУС СОБЕСЕДНИКА: {status}\n"
        f"ИНФО ИЗ СЕТИ: {web_data}\n"
        f"ПАМЯТЬ ЧАТА: {history_str}\n"
        f"СООБЩЕНИЕ: {message.text}\n\n"
        "ОТВЕТЬ СООТВЕТСТВЕННО ТОНУ ЮЗЕРА:"
    )

    try:
        response = model.generate_content(full_prompt)
        answer = response.text
        
        if answer:
            # Ставим реакции для стиля
            if is_admin: await message.react([types.ReactionTypeEmoji(emoji="🔥")])
            elif any(w in message.text.lower() for w in ['тупой', 'лох']): 
                await message.react([types.ReactionTypeEmoji(emoji="🌚")])

            memory.append({"role": "user", "content": message.text})
            memory.append({"role": "assistant", "content": answer})
            await message.answer(answer)
            
    except Exception as e:
        logger.error(f"API Error: {e}")
        await message.answer("Я занят пересборкой нейронов. Отвали на минуту.")

# Healthcheck для Render
async def handle(request):
    return web.Response(text="Idel is Online")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    
    # Сброс Conflict
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(8)
    await site.start()
    
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
