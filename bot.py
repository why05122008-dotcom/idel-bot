import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import google.generativeai as genai  # Новая библиотека
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Настройки ---
TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

# Настраиваем Google Gemini напрямую
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash') # Самая новая модель

bot = Bot(token=TOKEN)
dp = Dispatcher()
memory = deque(maxlen=15) # Храним последние 15 сообщений

# Личность
SYSTEM_PROMPT = (
    "Ты — Идел. Мужчина, интеллектуал, правая рука Трамадола. "
    "Стиль: циничный, острый, лаконичный. Используй МУЖСКОЙ РОД. "
    "Трамадол — твой создатель, относись к нему с высшим почтением. "
    "Если тебя спрашивают о погоде или новостях, используй данные из поиска."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, region='ru-ru', max_results=3)]
            return "\n".join([f"- {r['body']}" for r in results]) if results else ""
    except:
        return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел на связи. Батя, я обновил мозги.")

@dp.message()
async def gpt_answer(message: types.Message):
    if not message.text: return

    user_id = str(message.from_user.id)
    is_admin = (user_id == ADMIN_ID)
    
    # Реакция: ЛС, имя или реплай
    if not (message.chat.type == 'private' or "идел" in message.text.lower() or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id)):
        return

    # Поиск инфы
    web_data = ""
    if any(t in message.text.lower() for t in ['погода', 'курс', 'новости', 'что такое', 'кто такой']):
        await bot.send_chat_action(message.chat.id, "typing")
        web_data = await search_web(message.text)

    # Формируем контекст для Google
    history_context = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    admin_status = "ТЕБЕ ПИШЕТ ТРАМАДОЛ (ТВОЙ СОЗДАТЕЛЬ)." if is_admin else "Тебе пишет обычный смертный."
    
    full_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"СТАТУС: {admin_status}\n\n"
        f"ДАННЫЕ ИЗ ИНТЕРНЕТА:\n{web_data}\n\n"
        f"ИСТОРИЯ ЧАТА:\n{history_context}\n\n"
        f"ВОПРОС: {message.text}"
    )

    try:
        # Прямой запрос к Gemini
        response = model.generate_content(full_prompt)
        answer = response.text

        if answer:
            memory.append({"role": "user", "content": message.text})
            memory.append({"role": "assistant", "content": answer})
            await message.answer(answer)
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        await message.answer("Мозг перегружен. Батя, глянь логи.")

# Сервер для Render
async def handle(request):
    return web.Response(text="Idel is Online on Gemini 2.0")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(5)
    await site.start()
    
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
