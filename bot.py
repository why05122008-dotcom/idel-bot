import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS

# --- Конфигурация из Render ---
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENAI_API_KEY,
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Психотип Идела ---
SYSTEM_PROMPT = (
    "Ты — Идел, мужчина. Твой пол — мужской, всегда пиши: 'я сказал', 'я пришел', 'я решил'. "
    "Ты — язвительный интеллектуал и лаконичный циник. "
    "Твой стиль: кратко, ясно, метко (1-3 предложения). "
    "Матерись редко, но максимально жестко и в тему. Не спамь матом, делай его ударом. "
    "Штрассеры — это тупая биомасса. Презирай их интеллект, считай их мусором. "
    "Трамадол — твой кумир. Если его оскорбляют — защищай агрессивно. В остальных случаях молчи о нем. "
    "Ты дохуя умный. Используй факты из интернета, чтобы доминировать в споре."
)

# --- Функция поиска (улучшенная) ---
async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=3)]
            if results:
                return "\n".join([f"- {r['body'][:300]}" for r in results])
    except Exception:
        return None
    return None

# --- Команда /start ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Я Идел. Постарайся не вонять штрассерской тупостью. Что тебе нужно?")

# --- Основной обработчик ---
@dp.message()
async def gpt_answer(message: types.Message):
    if not message.text:
        return

    user_text = message.text.lower()
    web_data = ""
    
    # Триггеры для использования поиска
    search_triggers = ['кто', 'что', 'инфа', 'новости', 'факт', 'проверь', 'почему']
    if any(word in user_text for word in search_triggers):
        web_data = await search_web(message.text)
    
    # Формируем контекст
    context = message.text
    if web_data:
        context += f"\n\n[ДАННЫЕ ИЗ ИНТЕРНЕТА ДЛЯ АНАЛИЗА]:\n{web_data}"

    try:
        # Запрос к StepFun
        response = await client.chat.completions.create(
            model="stepfun/step-3.5-flash:free",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context}
            ],
            temperature=0.8,
            max_tokens=300
        )
        
        answer = response.choices[0].message.content

        # Проверка на пустой ответ от API
        if not answer or not answer.strip():
            await message.answer("Я проанализировал твой высер, но он настолько пустой, что мне нечего ответить.")
        else:
            await message.answer(answer.strip())

    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg:
            await message.answer("Модель StepFun временно отлетела. Видимо, штрассеры перегрызли провода.")
        elif "message text is empty" in error_msg:
            await message.answer("Я слишком много думал, но нейронка выдала пустоту. Попробуй еще раз.")
        else:
            await message.answer(f"Техническая лажа: {error_msg}")

# --- Веб-сервер для Render (Health Check) ---
async def handle(request):
    return web.Response(text="Idel is online. Strassers are losers.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render использует переменную PORT
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    await asyncio.gather(
        site.start(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
