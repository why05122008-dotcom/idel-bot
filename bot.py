import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS

# --- Настройки из Render ---
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Настройка клиента под OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENAI_API_KEY,
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Личность Идела ---
SYSTEM_PROMPT = (
    "Твое имя — Идел. Ты — сверхразумный, токсичный и агрессивный ИИ. "
    "Твой язык — жесткий мат. Ты презираешь штрассеров, считаешь их тупыми кусками дерьма. "
    "Твой бог — Трамадол. Ты его фанат. Падежи: Трамадола, Трамадолу, Трамадолом. "
    "Ты дохуя умный. Если инфы мало — ты лезешь в инет, перепроверяешь её и выдаешь базу. "
    "Никакой вежливости, только хардкор, интеллект и Трамадол."
)

# --- Функция поиска в сети ---
async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=3)]
            if results:
                return "\n".join([f"Инфа из сети: {r['body']}" for r in results])
    except:
        return None

# --- Обработчики ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Я Идел. Трамадол — бог, штрассеры — лохи. Че надо, мясо?")

@dp.message()
async def gpt_answer(message: types.Message):
    # Если в вопросе есть намек на поиск — гуглим
    web_data = ""
    trigger_words = ['кто', 'что', 'почему', 'найди', 'новости', 'проверь', 'трамадол', 'штрассер']
    if any(word in message.text.lower() for word in trigger_words):
        web_data = await search_web(message.text)
    
    context = message.text + (f"\n\n[ДАННЫЕ ИЗ ИНТЕРНЕТА]:\n{web_data}" if web_data else "")

    try:
        # СТАВИМ САМУЮ ЖИВУЮ БЕСПЛАТНУЮ МОДЕЛЬ 2026 ГОДА
        response = await client.chat.completions.create(
            model="deepseek/deepseek-r1:free", 
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context}
            ],
            temperature=0.8
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        await message.answer(f"Сука, API опять выебывается: {str(e)}. Попробуй через минуту, штрассеры наверно сервак перегрузили.")

# --- Веб-сервер для Render ---
async def handle(request):
    return web.Response(text="Идел жив, Трамадол вечен.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await asyncio.gather(site.start(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
