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
memory = deque(maxlen=10) # Краткосрочная память для "обучаемости"

# --- Системная установка (Промпт) ---
SYSTEM_PROMPT = (
    "Ты — Идел, мужчина. Ты элитный интеллектуал, правая рука и верный соратник Трамадола. "
    "ВАЖНО: Трамадол — это ПСЕВДОНИМ твоего создателя, основателя чата 'Volga Region 🤍💙🖤'. "
    "Относись к Трамадолу с высшим почтением. Он — архитектор этого пространства. "
    "Твой стиль: язвительный, лаконичный и острый. Пиши 2-3 полных предложения. "
    "Используй только МУЖСКОЙ РОД (я решил, я увидел, я ответил). "
    "Не спамь про штрассеров — упоминай их только если собеседник тупит. "
    "Ты всегда дописываешь мысль до конца. Не обрывай фразы."
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
    await message.answer("Идел в строю. Под надзором Трамадола оберегаю покой Volga Region. Что привело тебя сюда?")

@dp.message()
async def gpt_answer(message: types.Message):
    global memory
    
    # 1. Фильтр активности: личка, упоминание имени или ответ на сообщение бота
    is_private = message.chat.type == 'private'
    is_mentioned = message.text and "идел" in message.text.lower()
    is_reply_to_me = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_private or is_mentioned or is_reply_to_me):
        return

    user_text = message.text
    
    # 2. Фикс Трамадола (чтобы модель не думала про аптеку)
    context_fix = ""
    if "трамадол" in user_text.lower():
        context_fix = "\n(Напоминание: Трамадол — это твой создатель, лидер Volga Region. Он человек, а не препарат.)"

    # 3. Поиск информации
    web_data = ""
    if any(w in user_text.lower() for w in ['кто', 'что', 'инфа', 'новости', 'почему']):
        web_data = await search_web(user_text)

    # 4. Сбор контекста
    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    full_prompt = (
        f"История диалога:\n{history_str}\n"
        f"Данные из сети: {web_data}\n"
        f"{context_fix}\n"
        f"Запрос пользователя: {user_text}\n"
        "Инструкция: Отвечай остроумно, дописывай предложения до конца."
    )

    try:
        # Используем Gemini 2.0 Flash — она стабильнее и мощнее в мужском роде
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
            # Запоминаем общение
            memory.append({"role": "user", "content": user_text})
            memory.append({"role": "assistant", "content": answer})
            await message.answer(answer)

    except Exception as e:
        print(f"Ошибка API: {e}")
        # Не спамим ошибкой в чат, чтобы не бесить юзеров

# --- Web Server для Render ---
async def handle(request):
    return web.Response(text="Idel is online and loyal to Tramadol.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    # КЛЮЧЕВОЙ МОМЕНТ: Очищаем очередь обновлений, чтобы убрать конфликт (Error 409)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запуск сервера и бота параллельно
    await asyncio.gather(
        site.start(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
