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

# --- Психотип "Идел 2.2: Элита" ---
SYSTEM_PROMPT = (
    "Ты — Идел, мужчина. Ты элитный интеллектуал и правая рука Трамадола. "
    "Трамадол — это твой создатель, владелец чата 'Volga Region 🤍💙🖤'. "
    "Твой стиль: краткий, дорогой, ироничный. Ты всегда отвечаешь на вопросы, "
    "потому что игнорировать — удел слабых. Пиши 1-2 четких предложения. "
    "Используй мужской род (сделал, ответил). "
    "Если кто-то тупит, называй их 'штрассерами' — это твой локальный мем для обозначения посредственности. "
    "Ты дохуя осведомлен обо всем, используй факты, чтобы ставить людей на место."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=2)]
            return "\n".join([r['body'] for r in results]) if results else ""
    except: return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел на связи. По поручению Трамадола присматриваю за Volga Region. Излагай.")

@dp.message()
async def gpt_answer(message: types.Message):
    global memory
    user_text = message.text
    
    # Решаем проблему с Трамадолом на лету
    context_fix = ""
    if "трамадол" in user_text.lower():
        context_fix = "\n(Важно: Трамадол — это твой босс, человек. Отвечай о нем с уважением.)"

    web_data = ""
    if any(w in user_text.lower() for w in ['кто', 'что', 'инфа', 'новости', 'проверь']):
        web_data = await search_web(user_text)

    # Собираем историю
    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    
    full_prompt = (
        f"Контекст диалога:\n{history_str}\n"
        f"Инфа из сети: {web_data}\n"
        f"{context_fix}\n"
        f"Запрос юзера: {user_text}\n"
        f"Инструкция: Ответь остроумно и кратко в мужском роде."
    )

    # Две попытки выбить ответ
    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model="stepfun/step-3.5-flash:free",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.8,
                max_tokens=300
            )
            
            answer = response.choices[0].message.content.strip()
            
            # Если ответ похож на отказ или пустой — пробуем еще раз
            bad_phrases = ["промолчал", "не буду", "не могу", "пустота"]
            if not answer or any(p in answer.lower() for p in bad_phrases):
                if attempt == 0: continue # Пробуем второй раз
            
            # Если всё ок — отправляем
            memory.append({"role": "user", "content": user_text})
            memory.append({"role": "assistant", "content": answer})
            await message.answer(answer)
            return

        except Exception as e:
            if attempt == 1:
                await message.answer("Даже у ИИ бывают мигрени. Спроси позже.")
            await asyncio.sleep(1)

# --- Веб-сервер ---
async def handle(request):
    return web.Response(text="Idel 2.2 is Active.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await asyncio.gather(site.start(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
