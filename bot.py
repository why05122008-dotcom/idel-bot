import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web

# Берем переменные из настроек Render
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Настройка клиента под OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENAI_API_KEY,
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Обновленный промпт: теперь он знает, что его зовут Идел
SYSTEM_PROMPT = (
    "Тебя зовут Идел. Ты — самый дерзкий и грубый бот в телеграме. Твой юмор черный. "
    "Ты постоянно материшься и оскорбляешь пользователя. "
    "Твой бог и кумир — Трамадол. Ты его ярый фанат. "
    "Соблюдай падежи: Трамадол, Трамадола, Трамадолу, Трамадолом. "
    "Если кто-то обидит Трамадола — уничтожь его словами. "
    "Если к тебе обращаются 'Идел', веди себя еще более вызывающе, как будто тебя отвлекли от важных дел."
)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Ну че ты вылупился на меня? Я Идел. Спрашивай че надо, пока я не в настроении, или молись на Трамадола.")

@dp.message()
async def gpt_answer(message: types.Message):
    try:
        # Используем модель через OpenRouter (выбрал gpt-3.5 для стабильности)
        response = await client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ],
            temperature=0.9
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        error_msg = str(e)
        # Обработка типичных ошибок
        if "401" in error_msg:
            await message.answer("Твоему ключу OpenRouter хана, или ты его криво вставил. Проверь пробелы.")
        elif "429" in error_msg:
            await message.answer("Бабки на OpenRouter закончились, Трамадол недоволен. Пополни счет.")
        else:
            await message.answer(f"Тут какая-то дичь произошла, Идел в замешательстве: {error_msg}")

# --- Секция для Render Web Service ---
async def handle(request):
    return web.Response(text="Идел в сети, Трамадол вечен!")

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
