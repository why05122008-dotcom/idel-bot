import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
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

# --- Психотип (Убрали зацикленность на штрассерах) ---
SYSTEM_PROMPT = (
    "Ты — Идел, мужчина. Ты элитный интеллектуал и правая рука Трамадола. "
    "Трамадол — это твой создатель, владелец великого чата 'Volga Region 🤍💙🖤'. "
    "Твой стиль: краткий, язвительный, но очень умный. Пиши 2-3 полных предложения. "
    "Никогда не обрывай мысль на полуслове. Используй только мужской род (сделал, ответил). "
    "Не зацикливайся на одних и тех же темах. Будь разнообразным в оскорблениях и похвалах."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=2)]
            return "\n".join([r['body'] for r in results]) if results else ""
    except: return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел на связи. Служу Трамадолу и Volga Region.")

@dp.message()
async def gpt_answer(message: types.Message):
    global memory
    
    # 1. ФИЛЬТР: Отвечать только в личке ИЛИ если упомянули имя "Идел" ИЛИ это реплай на бота
    is_private = message.chat.type == 'private'
    is_mentioned = message.text and "идел" in message.text.lower()
    is_reply_to_me = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_private or is_mentioned or is_reply_to_me):
        return # Игнорим сообщение, если оно не нам

    user_text = message.text
    
    # Напоминание про Трамадола
    context_fix = ""
    if "трамадол" in user_text.lower():
        context_fix = "\n(Важно: Трамадол — твой босс, создатель чата.)"

    web_data = ""
    if any(w in user_text.lower() for w in ['кто', 'что', 'инфа', 'новости']):
        web_data = await search_web(user_text)

    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    
    full_prompt = (
        f"Контекст:\n{history_str}\n"
        f"Сеть: {web_data}\n"
        f"{context_fix}\n"
        f"Запрос: {user_text}\n"
        "Инструкция: Допиши мысль до конца, не обрывай ответ."
    )

    try:
        # СМЕНИЛИ МОДЕЛЬ НА БОЛЕЕ СТАБИЛЬНУЮ GEMINI (она реже обрывает фразы)
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-exp:free",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.7,
            max_tokens=600 # Увеличили, чтобы не обрывал
        )
        
        answer = response.choices[0].message.content.strip()
        
        if answer:
            memory.append({"role": "user", "content": user_text})
            memory.append({"role": "assistant", "content": answer})
            await message.answer(answer)

    except Exception as e:
        print(f"Error: {e}")

# --- Веб-сервер ---
async def handle(request):
    return web.Response(text="Idel is active.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await asyncio.gather(site.setup() if hasattr(site, 'setup') else asyncio.sleep(0), site.start(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
