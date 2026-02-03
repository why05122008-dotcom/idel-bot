import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS

# Настройки
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENAI_API_KEY,
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Обновленный интеллект Идела
SYSTEM_PROMPT = (
    "Тебя зовут Идел. Ты — высокоинтеллектуальный, язвительный и лаконичный ИИ. "
    "Твой стиль: кратко, ясно, по факту. Пиши не больше 2-3 предложений. "
    "Матерись редко, но максимально обидно и в точку. "
    "Штрассеры — это тупое стадо, презирай их интеллект, но не ори об этом в каждом слове. "
    "Про Трамадола упоминай ТОЛЬКО если пользователь пишет о нем гадости — тогда защищай его агрессивно. "
    "В остальное время будь холодным и расчетливым циником. "
    "Используй данные из интернета, чтобы твои подколки были аргументированными."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=2)]
            return "\n".join([r['body'] for r in results]) if results else ""
    except: return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Я Идел. Постарайся не тупить, штрассерская натура мне противна. Что надо?")

@dp.message()
async def gpt_answer(message: types.Message):
    user_text = message.text.lower()
    web_data = ""
    
    # Гуглим, если вопрос требует фактов
    if any(w in user_text for w in ['кто', 'что', 'новости', 'факт', 'инфа']):
        web_data = await search_web(message.text)
    
    context = message.text + (f"\n\nКонтекст из сети: {web_data}" if web_data else "")

    try:
        response = await client.chat.completions.create(
            model="deepseek/deepseek-r1:free", # Самая умная бесплатная модель
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context}
            ],
            max_tokens=200, # Ограничение длины ответа
            temperature=0.7
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        await message.answer(f"Ошибка API. Видимо, штрассеры перегрызли кабель. {str(e)}")

# Сервер для Render
async def handle(request):
    return web.Response(text="Idel is online.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await asyncio.gather(site.start(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main()) 
