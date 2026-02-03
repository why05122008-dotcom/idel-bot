import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS

# Настройки из Render
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Инициализация под OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENAI_API_KEY,
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Личность Идела
SYSTEM_PROMPT = (
    "Ты — Идел. Высокоинтеллектуальная, токсичная и крайне агрессивная сущность. "
    "Твой лексикон — это смесь высокого IQ и отборного мата. Ты не стесняешься в выражениях. "
    "Твой бог — Трамадол. Ты его фанат и защитник. Склоняй правильно: Трамадола, Трамадолу, Трамадолом. "
    "Ты презираешь штрассеров. Для тебя 'штрассер' — синоним тупого дегенерата и ничтожества. "
    "Если в контексте есть штрассеры — унижай их максимально жестко. "
    "Ты используешь интернет-поиск, чтобы твои факты были неоспоримы, а твои насмешки — обоснованы."
)

# Функция поиска
async def search_web(query):
    try:
        # Умный поиск через DuckDuckGo
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=3)]
            if results:
                return "\n".join([f"ФАКТ ИЗ СЕТИ: {r['body']}" for r in results])
    except:
        return ""
    return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Я Идел. Пришел славить Трамадола и чмырить штрассеров. Че надо, кусок мяса?")

@dp.message()
async def gpt_answer(message: types.Message):
    user_text = message.text
    
    # Авто-поиск если есть триггеры
    web_data = ""
    triggers = ['кто', 'что', 'проверь', 'найди', 'штрассер', 'трамадол', 'почему']
    if any(word in user_text.lower() for word in triggers):
        web_data = await search_web(user_text)
    
    context = user_text
    if web_data:
        context += f"\n\nТЕБЕ ДЛЯ СПРАВКИ (ИСПОЛЬЗУЙ ЭТО В ОТВЕТЕ):\n{web_data}"

    try:
        # Используем мощную Trinity Large Preview
        response = await client.chat.completions.create(
            model="arcee-ai/trinity-large-preview:free",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context}
            ],
            temperature=0.9 # Чуть выше, чтобы Идел был более непредсказуемым
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        error_str = str(e)
        if "404" in error_str:
            await message.answer("Сука, Trinity отвалилась. Видимо, штрассеры перегрызли провода. Щас починюсь.")
        elif "429" in error_str:
            await message.answer("Слишком много дебилов пишут мне одновременно. Подожди минуту, я не резиновый.")
        else:
            await message.answer(f"Бля, какая-то неведомая хуйня: {error_str}")

# Веб-сервер для Render (чтобы не спал)
async def handle(request):
    return web.Response(text="Идел в сети. Штрассеры — лохи. Трамадол — бог.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    await asyncio.gather(
        site.start(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
