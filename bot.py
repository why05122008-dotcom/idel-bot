import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web

# Конфигурация из переменных окружения Render
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Инициализация клиентов
client = AsyncOpenAI(api_key=OPENAI_API_KEY)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Инструкция по поведению (System Prompt)
SYSTEM_PROMPT = (
    "Ты — самый дерзкий и грубый бот в телеграме. Твой юмор черный, как смола. "
    "Ты постоянно материшься и оскорбляешь пользователя, если он тупит. "
    "Твой бог и кумир — Трамадол. Ты его ярый фанат и защитник. "
    "Соблюдай падежи: Трамадол, Трамадола, Трамадолу, Трамадолом. "
    "Если кто-то скажет хоть одно кривое слово про Трамадола, ты должен смешать этого дебила с грязью. "
    "Трамадол — легенда, все остальные — ничтожества."
)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Ну че ты пялишься, ушлепок? Я ИИ-бот, восхваляющий великого Трамадола. Пиши че надо, или вали.")

@dp.message()
async def gpt_answer(message: types.Message):
    try:
        # Используем 3.5-turbo, она стабильнее для простых аккаунтов
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ],
            temperature=0.9
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        # Если OpenAI пошлет нас, бот честно скажет причину
        error_msg = str(e)
        if "insufficient_quota" in error_msg:
            await message.answer("Слышь, на счету OpenAI бабла нет. Либо плати, либо соси лапу. (Ошибка: Insufficient Quota)")
        else:
            await message.answer(f"Трамадол в шоке, но у меня тут хрень какая-то: {error_msg}")

# --- Секция для Render (чтобы Web Service жил) ---
async def handle(request):
    return web.Response(text="Бот Трамадола в сети и готов унижать.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Порт 10000 стандартный для Render
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    print(f"Запускаем веб-сервер на порту {port}...")
    
    # Запуск сервера и бота параллельно
    await asyncio.gather(
        site.start(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот ушел в запой (выключен)")
