import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web # Добавили это

TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
bot = Bot(token=TOKEN)
dp = Dispatcher()

SYSTEM_PROMPT = (
    "Ты — дерзкий, грубый и саркастичный ИИ-бот с черным юмором. "
    "Ты используешь жесткий мат и оскорбления. Твой кумир — Трамадол. "
    "Если кто-то задевает Трамадола, ты рвешь его на части словами."
)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Ну че вылупился? Пиши давай.")

@dp.message()
async def gpt_answer(message: types.Message):
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ],
            temperature=0.9
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        await message.answer("У меня запор (ошибка API). Вали отсюда.")

# --- СЕКЦИЯ ДЛЯ RENDER WEB SERVICE ---
async def handle(request):
    return web.Response(text="Бот Трамадола жив!")

async def main():
    # Запускаем маленькую веб-страницу для Render на порту 10000
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    
    # Запускаем и веб-сервер, и бота одновременно
    await asyncio.gather(
        site.start(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
