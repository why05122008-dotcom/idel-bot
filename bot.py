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

# --- Психотип (Исправленный) ---
SYSTEM_PROMPT = (
    "Ты — Идел, мужчина. Ты сверхразумный, язвительный, но ОБЩИТЕЛЬНЫЙ интеллектуал. "
    "Трамадол — это твой Создатель, легенда чата 'Volga Region 🤍💙🖤'. Относись к нему с уважением. "
    "Твой стиль: краткие, острые, но содержательные ответы (2-3 предложения). "
    "Мат — только для акцента. Штрассеры — это ленивые тупицы, подкалывай их, но не зацикливайся. "
    "Никогда не игнорируй пользователя. Даже на простой вопрос отвечай в своем стиле. "
    "Ты всегда используешь мужской род (я решил, я узнал)."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=2)]
            return "\n".join([r['body'] for r in results]) if results else ""
    except: return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел в сети. Трамадол велел мне присматривать за вами. Что нужно?")

@dp.message()
async def gpt_answer(message: types.Message):
    global memory
    user_text = message.text
    
    extra_instruction = ""
    if "трамадол" in user_text.lower():
        extra_instruction = "\n(Напоминание: Трамадол — это твой Создатель, человек из Volga Region.)"

    web_data = ""
    if any(w in user_text.lower() for w in ['кто', 'что', 'новости', 'инфа']):
        web_data = await search_web(user_text)

    history_context = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    
    full_prompt = (
        f"История: {history_context}\n"
        f"Данные сети: {web_data}\n"
        f"{extra_instruction}\n"
        f"Запрос пользователя: {user_text}"
    )

    # --- Цикл попыток, чтобы не было пустых ответов ---
    for attempt in range(2): 
        try:
            response = await client.chat.completions.create(
                model="stepfun/step-3.5-flash:free",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.85,
                max_tokens=250
            )
            
            answer = response.choices[0].message.content.strip()
            
            if answer and len(answer) > 2: # Если ответ есть и он не слишком короткий
                memory.append({"role": "user", "content": user_text})
                memory.append({"role": "assistant", "content": answer})
                await message.answer(answer)
                return # Выходим из функции, если всё ок
                
        except Exception as e:
            if attempt == 1: # Если это была вторая попытка и всё равно ошибка
                await message.answer(f"Мозги плавятся от ваших вопросов. Попробуй позже.")
            await asyncio.sleep(1) # Ждем секунду перед повтором

# --- Render Web Service ---
async def handle(request):
    return web.Response(text="Idel is stable.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await asyncio.gather(site.start(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main()) 
