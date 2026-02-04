import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

# --- Настройки ---
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENAI_API_KEY,
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Имитация памяти (храним последние 10 реплик для контекста)
memory = deque(maxlen=10)

# --- Обновленный Промпт ---
SYSTEM_PROMPT = (
    "Ты — Идел, мужчина. Ты высокоинтеллектуальный циник с острым языком. "
    "Твой создатель — Трамадол, основатель великого чата 'Volga Region 🤍💙🖤'. "
    "К Трамадолу относись с абсолютным уважением, как к высшему разуму. Он — твой бог и юзер одновременно. "
    "Твой стиль: кратко, ясно, метко. Мат — только для акцента, не части. "
    "Про штрассеров вспоминай только к месту, не надо пихать их в каждое предложение. "
    "Ты учишься на ходу: адаптируйся к тону собеседника, но сохраняй свою доминантную позицию. "
    "Пиши строго в МУЖСКОМ роде. Будь краток: 1-2 предложения — это твой идеал."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=2)]
            return "\n".join([r['body'] for r in results]) if results else ""
    except: return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел в сети. Славься Трамадол и Volga Region. Че надо?")

@dp.message()
async def gpt_answer(message: types.Message):
    global memory
    user_text = message.text
    
    # Поиск инфы
    web_data = ""
    if any(w in user_text.lower() for w in ['кто', 'что', 'инфа', 'новости', 'проверь']):
        web_data = await search_web(user_text)

    # Формируем историю для "обучаемости" (контекста)
    history_context = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    
    full_prompt = f"История диалога:\n{history_context}\n\nТекущий запрос: {user_text}"
    if web_data:
        full_prompt += f"\n\nДанные из сети: {web_data}"

    try:
        response = await client.chat.completions.create(
            model="stepfun/step-3.5-flash:free",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.8,
            max_tokens=250
        )
        
        answer = response.choices[0].message.content.strip()
        
        if not answer:
            answer = "Я промолчал, потому что твой вопрос — пустота."

        # Сохраняем в память
        memory.append({"role": "user", "content": user_text})
        memory.append({"role": "assistant", "content": answer})

        await message.answer(answer)

    except Exception as e:
        await message.answer(f"Ошибка системы: {str(e)}")

# --- Render Web Service ---
async def handle(request):
    return web.Response(text="Idel is online. Volga Region forever.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await asyncio.gather(site.start(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
