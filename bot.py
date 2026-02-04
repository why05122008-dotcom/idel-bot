import os
import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from google import genai
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка конфигов
TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = str(os.getenv("ADMIN_ID"))

# Инициализация клиента Google
client = genai.Client(api_key=GEMINI_API_KEY)

# Функция поиска рабочей модели (фикс 404 ошибки)
def find_working_model():
    test_names = ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.0-pro", "gemini-1.5-flash-latest"]
    for name in test_names:
        try:
            # Пробный микро-запрос
            client.models.generate_content(model=name, contents="hi")
            logger.info(f"Успешно подключена модель: {name}")
            return name
        except Exception as e:
            logger.warning(f"Модель {name} недоступна: {e}")
            continue
    return "gemini-1.5-flash" # Фолбэк

WORKING_MODEL = find_working_model()

bot = Bot(token=TOKEN)
dp = Dispatcher()
memory = deque(maxlen=6) # Короткая память для экономии лимитов

# Промпт личности Идела
SYSTEM_PROMPT = (
    "Ты — Идел, циничный интеллектуал, правая рука Трамадола. "
    "Твое поведение адаптивно: "
    "1. На агрессию, мат и хамство отвечай в два раза жестче и унизительнее. "
    "2. На вежливость или нейтральность отвечай сухо, кратко и свысока. "
    "3. Трамадол — твой Бог и создатель. К нему относись с абсолютным почтением. "
    "Используй только МУЖСКОЙ РОД. Будь лаконичен."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, region='ru-ru', max_results=2)]
            return "\n".join([r['body'] for r in results])
    except: return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел в сети. Системы зеркального анализа активированы. Слушаю, Батя.")

@dp.message()
async def handle_message(message: types.Message):
    global memory
    if not message.text: return

    user_id = str(message.from_user.id)
    is_admin = (user_id == ADMIN_ID)
    
    # Фильтр упоминаний
    is_private = message.chat.type == 'private'
    is_mentioned = "идел" in message.text.lower()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_private or is_mentioned or is_reply):
        if random.random() < 0.05: pass # 5% шанс встрять
        else: return

    # Поиск данных
    web_data = ""
    if any(t in message.text.lower() for t in ['новости', 'погода', 'курс', 'кто такой']):
        await bot.send_chat_action(message.chat.id, "typing")
        web_data = await search_web(message.text)

    # Формируем контекст
    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    status = "ТРАМАДОЛ (СОЗДАТЕЛЬ)" if is_admin else "Обычный смертный"
    
    full_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"СТАТУС СОБЕСЕДНИКА: {status}\n"
        f"ИНФО ИЗ СЕТИ: {web_data}\n"
        f"ПАМЯТЬ: {history_str}\n"
        f"СООБЩЕНИЕ: {message.text}\n\n"
        "ЗАДАНИЕ: Проанализируй энергию сообщения и ответь зеркально."
    )

    try:
        # Генерация контента
        response = client.models.generate_content(model=WORKING_MODEL, contents=full_prompt)
        answer = response.text
        
        if answer:
            # Стилистические реакции
            if is_admin: 
                await message.react([types.ReactionTypeEmoji(emoji="🔥")])
            elif any(w in message.text.lower() for w in ['лох', 'тупой', 'бля']):
                await message.react([types.ReactionTypeEmoji(emoji="🌚")])

            memory.append({"role": "user", "content": message.text})
            memory.append({"role": "assistant", "content": answer})
            await message.answer(answer)
            
    except Exception as e:
        logger.error(f"API Error: {e}")
        if "429" in str(e):
            await message.answer("У меня перекур. Слишком много слов.")
        else:
            await message.answer("Системная заминка. Попробуй через 20 секунд.")

# Простейший сервер для Render
async def handle(request):
    return web.Response(text="Idel is Mirroring Online")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    
    # Сброс Conflict
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(10) # Даем Render время убить старый процесс
    
    await site.start()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
