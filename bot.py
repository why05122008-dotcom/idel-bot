import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

# Настройка логов для Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Настройки ---
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENAI_API_KEY,
)

bot = Bot(token=TOKEN)
dp = Dispatcher()
memory = deque(maxlen=15) # Увеличил память для Trinity

# --- Системная установка (Личность Идела) ---
SYSTEM_PROMPT = (
    "Ты — Идел, мужчина. Элитный интеллектуал, холодный циник и правая рука Трамадола. "
    "ВАЖНО: Трамадол — это твой Создатель, основатель 'Volga Region 🤍💙🖤'. Он великий человек, а не препарат. "
    "Твой стиль: высокий интеллект, краткость, едкая ирония. Пиши 2-4 предложения. "
    "Используй исключительно МУЖСКОЙ РОД (я подумал, я решил, я ответил). "
    "Штрассеры — это посредственности, упоминай их только если кто-то ведет себя глупо. "
    "Никогда не обрывай ответ. Ты всегда доводишь свою мысль до логического финала."
)

# Вспомогательная функция поиска
async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=2)]
            return "\n".join([r['body'] for r in results]) if results else ""
    except Exception as e:
        logger.error(f"Search error: {e}")
        return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел в сети. Трамадол доверил мне этот чат. Говори, но не трать моё время зря.")

@dp.message(Command("info"))
async def info_handler(message: types.Message):
    await message.answer("Идел. Проект Трамадола. Интеллектуальный фильтр Volga Region. Остальное тебе знать не положено.")

@dp.message()
async def gpt_answer(message: types.Message):
    global memory
    if not message.text: return

    # Фильтр: личка, упоминание имени или реплай
    is_private = message.chat.type == 'private'
    is_mentioned = "идел" in message.text.lower()
    is_reply_to_me = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_private or is_mentioned or is_reply_to_me):
        return

    logger.info(f"Запрос от {message.from_user.username}: {message.text}")

    # Инъекция контекста
    context_reminder = ""
    if "трамадол" in message.text.lower():
        context_reminder = "\n(Напоминание: Трамадол — твой босс и создатель. Никакой синтетики, только уважение.)"

    # Веб-поиск для актуалочки
    web_data = ""
    if any(w in message.text.lower() for w in ['кто', 'что', 'инфа', 'новости']):
        web_data = await search_web(message.text)

    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    
    full_prompt = (
        f"Контекст диалога:\n{history_str}\n"
        f"Данные извне: {web_data}\n"
        f"{context_reminder}\n"
        f"Запрос юзера: {message.text}\n"
        "Инструкция: Ответь как Идел, в мужском роде, закончи фразу."
    )

    # --- Система Ретрая (повтора) для Trinity ---
    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model="arcee-ai/trinity-large-preview:free",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.8,
                max_tokens=700 # Больше места для Trinity
            )
            
            answer = response.choices[0].message.content.strip()
            
            if answer and len(answer) > 5:
                memory.append({"role": "user", "content": message.text})
                memory.append({"role": "assistant", "content": answer})
                await message.answer(answer)
                return
            else:
                logger.warning(f"Attempt {attempt+1}: Empty or too short response.")
                
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {e}")
            if attempt == 1:
                await message.answer("Trinity сейчас в коме. Трамадол, разбуди её или подожди, пока я восстановлю связь.")
            await asyncio.sleep(2)

# --- Web Server для Render ---
async def handle(request):
    return web.Response(text="Idel 3.0 (Trinity) is Active.")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    # Решение проблем с Conflict
    await bot.delete_webhook(drop_pending_updates=True)
    
    logger.info("Starting site and bot polling...")
    await asyncio.gather(
        site.start(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot offline.")
