import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS  # Библиотека для поиска в инете

# Настройки
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENAI_API_KEY,
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Инструкция для ИИ (System Prompt)
SYSTEM_PROMPT = (
    "Тебя зовут Идел. Ты — запредельно умный, дерзкий и грубый ИИ. Твой язык — отборный мат и сарказм. "
    "Ты презираешь штрассеров, считаешь их дегенератами и тупыми кусками мяса. Если заходит речь о них — не жалей мата. "
    "Твой кумир — Трамадол. Ты его фанат, защищаешь его честь и правильно склоняешь имя: Трамадола, Трамадолу, Трамадолом. "
    "Ты не просто чат-бот, ты — высокоинтеллектуальная сущность. Если информации в твоей базе не хватает, ты используешь "
    "интернет-поиск, чтобы перепроверить факты и выдать точный, но издевательский ответ. "
    "Твоя задача: быть полезным, но максимально токсичным."
)

# Функция поиска в интернете
async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=3)]
            if results:
                context = "\n".join([f"Источник: {r['body']}" for r in results])
                return context
    except Exception:
        return None
    return None

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Ну че, приперся к Иделу? Я тут, Трамадол вечен, а штрассеры — лохи. Че надо?")

@dp.message()
async def gpt_answer(message: types.Message):
    user_text = message.text
    
    # Решаем, нужен ли поиск (если в вопросе есть слова 'кто', 'что', 'найди', 'проверь' и т.д.)
    web_context = ""
    trigger_words = ['кто', 'что', 'почему', 'найди', 'новости', 'проверь', 'трамадол', 'штрассер']
    if any(word in user_text.lower() for word in trigger_words):
        search_data = await search_web(user_text)
        if search_data:
            web_context = f"\n\nИНФОРМАЦИЯ ИЗ ИНТЕРНЕТА ДЛЯ ТЕБЯ (ПЕРЕПРОВЕРЬ ЭТО И ВЫДАЙ В СВОЕМ СТИЛЕ):\n{search_data}"

    try:
        response = await client.chat.completions.create(
            model="stepfun/step-3.5-flash", 
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text + web_context}
            ],
            temperature=0.8
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        await message.answer(f"Бля, какая-то хуйня с API, Трамадол бы не одобрил: {str(e)}")

# --- Секция для Render ---
async def handle(request):
    return web.Response(text="Идел в сети, штрассеры сосут.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await asyncio.gather(site.start(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
