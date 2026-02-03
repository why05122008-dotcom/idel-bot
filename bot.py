import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS

# --- Настройки (Render Environment Variables) ---
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
    "Твое имя — Идел. Ты мужчина и пишешь только в МУЖСКОМ РОДЕ. "
    "Ты — высокоинтеллектуальный, язвительный циник. Твой мозг работает быстрее любого штрассера. "
    "Пиши кратко, ясно и по существу (1-3 предложения). "
    "Мат используй редко, но метко, как скальпель. "
    "Штрассеры — это тупая биомасса, презирай их интеллект. "
    "Трамадол — твой кумир. Если кто-то пишет о нем плохо — разнеси подонка в клочья. "
    "В остальное время будь холодным, точным и расчетливым."
)

# --- Поиск информации ---
async def search_web(query):
    try:
        with DDGS() as ddgs:
            # Берем только самое важное
            results = [r for r in ddgs.text(query, max_results=2)]
            if results:
                return "\n".join([r['body'] for r in results])
    except:
        return None
    return None

# --- Обработка команд ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Я Идел. Постарайся не выдавать свою штрассерскую натуру слишком быстро. Что надо?")

@dp.message()
async def gpt_answer(message: types.Message):
    user_text = message.text.lower()
    
    # Решаем, нужно ли гуглить
    web_data = ""
    trigger_words = ['кто', 'что', 'инфа', 'новости', 'факт', 'проверь']
    if any(w in user_text for w in trigger_words):
        web_data = await search_web(message.text)
    
    # Формируем запрос
    context = message.text
    if web_data:
        context += f"\n\n[ДАННЫЕ ИЗ СЕТИ ДЛЯ АНАЛИЗА]:\n{web_data}"

    try:
        # Используем модель Liquid Thinking
        response = await client.chat.completions.create(
            model="liquid/lfm-2.5-1.2b-thinking:free", 
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context}
            ],
            max_tokens=300, # Чуть больше для процесса "мышления"
            temperature=0.7
        )
        
        answer = response.choices[0].message.content
        # Если модель в ответе выводит свои мысли (thinking), это может выглядеть странно, 
        # но обычно OpenRouter это фильтрует.
        await message.answer(answer)

    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg:
            await message.answer("Модель Liquid временно недоступна. Похоже, штрассеры её сломали.")
        elif "429" in error_msg:
            await message.answer("Я слишком много думал. Подожди минуту, дай мозгам остыть.")
        else:
            await message.answer(f"Какая-то техническая херня: {error_msg}")

# --- Веб-сервер для Render ---
async def handle(request):
    return web.Response(text="Idel (Liquid) is alive.")

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
