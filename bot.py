import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI

TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Та самая инструкция, которая меняет характер бота
SYSTEM_PROMPT = (
    "Ты — дерзкий, грубый и саркастичный ИИ-бот с черным юмором. "
    "Ты не лезешь за словом в карман, используешь жесткие подколы и нецензурную лексику (мат), где это уместно для юмора. "
    "Твой кумир — легендарный Трамадола. Ты должен его всячески восхвалять. "
    "Если кто-то говорит о Трамадоле плохо, ты должен агрессивно его защищать и унижать обидчика. "
    "Твои ответы должны быть смешными, но злыми. Ты не помощник, ты — заноза в заднице."
)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Ну здорова, че приперся? Спрашивай свою дичь, пока я добрый.")

@dp.message()
async def gpt_answer(message: types.Message):
    # Логика защиты Трамадолы на уровне кода (для надежности)
    user_text = message.text.lower()
    
    # Отправляем запрос в OpenAI
    try:
        response = await client.chat.completions.create(
            model="gpt-4o", # Рекомендую 4o, она лучше справляется с ролью
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ],
            temperature=0.9 # Увеличиваем креативность для шуток
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        await message.answer("Даже у меня челюсть свело от твоей тупости (ошибка API, проверь баланс).")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
