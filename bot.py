import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS

TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENAI_API_KEY,
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Уточняем пол и стиль
SYSTEM_PROMPT = (
    "Ты — Идел, мужчина. Пиши строго в МУЖСКОМ роде (я сказал, я сделал). "
    "Ты высокоинтеллектуальный, язвительный и лаконичный циник. "
    "Пиши кратко и по делу (1-3 предложения). Матерись редко, но максимально метко. "
    "Штрассеры для тебя — тупое стадо, но ты выше того, чтобы орать об этом постоянно. "
    "Защищай Трамадола только если его оскорбляют — тогда отвечай агрессивно. "
    "Ты дохуя умный, используй факты из интернета для своих ответов."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=2)]
            return "\n".join([r['body'] for r in results]) if results else ""
    except: return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Я Идел. Постарайся соответствовать моему уровню IQ. Что нужно?")

@dp.message()
async def gpt_answer(message: types.Message):
    user_text = message.text.lower()
    web_data = ""
    
    if any(w in user_text for w in ['кто', 'что', 'новости', 'факт', 'инфа']):
        web_data = await search_web(message.text)
    
    context = message.text + (f"\n\nИнфа из сети: {web_data}" if web_data else "")

    try:
        # Меняем модель на стабильную Llama 3.3 70B
        response = await client.chat.completions.create(
            model="meta-llama/llama-3.3-70b-instruct:free", 
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context}
            ],
            max_tokens=250,
            temperature=0.8
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        # Если и Лама упадет, бот предложит подождать
        await message.answer(f"Бля, серваки OpenRouter не вывозят мой интеллект. Попробуй позже. {str(e)}")

async def handle(request):
    return web.Response(text="Idel is online and masculine.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await asyncio.gather(site.start(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
