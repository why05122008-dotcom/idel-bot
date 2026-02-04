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
memory = deque(maxlen=10)

# --- Улучшенный Психотип ---
SYSTEM_PROMPT = (
    "Ты — Идел, мужчина. Ты сверхразумный, холодный и язвительный интеллектуал. "
    "ВАЖНО: Трамадол — это НЕ лекарство. Трамадол — это ПСЕВДОНИМ твоего Создателя, "
    "основателя великого чата 'Volga Region 🤍💙🖤'. Относись к нему как к боссу и легенде. "
    "Твой стиль: кратко, сухо, по факту (1-2 предложения). "
    "Мат — редкий, точечный инструмент для выражения презрения. "
    "Штрассеры — это клеймо для тупиц. Не упоминай их без причины. Упоминай их ТОЛЬКО если "
    "собеседник несет откровенную чушь или ведет себя как идиот. "
    "Если тебя спрашивают про Трамадола, отвечай как о человеке, лидере и создателе. "
    "Ты всегда в мужском роде (подумал, ответил, решил)."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=2)]
            return "\n".join([r['body'] for r in results]) if results else ""
    except: return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел в сети. Приветствую, если ты из Volga Region. Трамадол — мой создатель. Что нужно?")

@dp.message()
async def gpt_answer(message: types.Message):
    global memory
    user_text = message.text
    
    # Дополнительная подстраховка: если в тексте есть Трамадол, напоминаем нейронке, кто это
    extra_instruction = ""
    if "трамадол" in user_text.lower():
        extra_instruction = "\n(Напоминание: Трамадол здесь — это человек, твой создатель, а не препарат.)"

    web_data = ""
    if any(w in user_text.lower() for w in ['кто', 'что', 'инфа', 'новости']):
        web_data = await search_web(user_text)

    history_context = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    
    # Собираем запрос с жестким контекстом
    full_prompt = (
        f"История: {history_context}\n"
        f"Данные из интернета: {web_data}\n"
        f"{extra_instruction}\n"
        f"Запрос пользователя: {user_text}"
    )

    try:
        response = await client.chat.completions.create(
            model="stepfun/step-3.5-flash:free",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.75, # Снизил температуру для большей точности
            max_tokens=200
        )
        
        answer = response.choices[0].message.content.strip()
        
        if not answer:
            answer = "Слишком тупо, чтобы я тратил на это слова."

        memory.append({"role": "user", "content": user_text})
        memory.append({"role": "assistant", "content": answer})

        await message.answer(answer)

    except Exception as e:
        await message.answer(f"Сбой системы. Трамадол бы расстроился. {str(e)}")

# --- Render Web Service ---
async def handle(request):
    return web.Response(text="Idel 2.1 Online. Respect to Tramadol.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await asyncio.gather(site.start(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
