import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

# --- Конфигурация ---
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENAI_API_KEY,
)

bot = Bot(token=TOKEN)
dp = Dispatcher()
memory = deque(maxlen=10)

# --- Промпт ---
SYSTEM_PROMPT = (
    "Ты — Идел, мужчина. Элитный интеллектуал и соратник Трамадола. "
    "Трамадол — твой создатель, основатель чата 'Volga Region 🤍💙🖤'. "
    "Твой стиль: язвительный, лаконичный. Пиши 2-3 предложения. "
    "Используй мужской род. Не обрывай фразы. "
    "Отвечай только если к тебе обратились или если это уместно."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=2)]
            return "\n".join([r['body'] for r in results]) if results else ""
    except:
        return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел в строю. Трамадол и Volga Region под моей защитой.")

@dp.message()
async def gpt_answer(message: types.Message):
    global memory
    
    # Реагируем на имя, реплаи или личку
    is_private = message.chat.type == 'private'
    is_mentioned = message.text and "идел" in message.text.lower()
    is_reply_to_me = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_private or is_mentioned or is_reply_to_me):
        return

    user_text = message.text
    context_fix = "\n(Напоминание: Трамадол — твой босс, создатель Volga Region.)" if "трамадол" in user_text.lower() else ""

    web_data = ""
    if any(w in user_text.lower() for w in ['кто', 'что', 'инфа']):
        web_data = await search_web(user_text)

    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    full_prompt = f"История:\n{history_str}\nСеть: {web_data}\n{context_fix}\nЗапрос: {user_text}\nИнструкция: Дописывай ответ до конца."

    try:
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-exp:free",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.8,
            max_tokens=500
        )
        answer = response.choices[0].message.content.strip()
        if answer:
            memory.append({"role": "user", "content": user_text})
            memory.append({"role": "assistant", "content": answer})
            await message.answer(answer)
    except Exception as e:
        print(f"API Error: {e}")

async def handle(request):
    return web.Response(text="Idel is online.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    # КРИТИЧЕСКИ ВАЖНО: удаляем вебхук и старые сообщения перед стартом
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("Идел запускается...")
    await asyncio.gather(
        site.start(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
