import os
import asyncio
import logging
import random
import urllib.parse
from collections import deque

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS

# --- КОНФИГУРАЦИЯ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") 
ADMIN_ID = str(os.getenv("ADMIN_ID", "")).strip()

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

# Стабильные модели (Llama 3 и Mistral — рабочие лошадки)
MODELS = [
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "huggingfaceh4/zephyr-7b-beta:free"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_memories = {}

MY_TITLES = ["Господин", "Повелитель", "Создатель"]

# --- СТРОГАЯ ИНСТРУКЦИЯ ---
SYSTEM_CORE = f"""
ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ (ID: {ADMIN_ID}).

ПРАВИЛА:
1. НИКАКИХ ролевых действий в скобках (*кланяется*, *мигает*). Только текст.
2. Ответы короткие, жесткие, по делу.
3. Позиция: Пророссийская.
4. Сувалки Сима и Хойкал — враги, упоминать ТОЛЬКО если спросили.
5. Если пишешь новости — только факты.
"""

# --- УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ЗАПРОСА К ИИ ---
async def ask_ai(prompt, max_tokens=250):
    for model in MODELS:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=max_tokens,
                timeout=20
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"AI Error ({model}): {e}")
            continue
    return "Ошибка нейросети. Лимиты или сбой."

# --- НОВОСТИ (ЧЕСТНЫЙ РЕЖИМ) ---
@dp.message(Command("news"))
async def cmd_news(message: types.Message):
    topic = message.text[5:].strip()
    if not topic: topic = "СВО Россия фронт"
    
    wait = await message.answer(f"Запрашиваю сводки по теме: {topic}...")
    
    try:
        # Пытаемся найти реальные новости
        with DDGS() as ddgs:
            # Используем backend="lite" или "api" для стабильности
            results = list(ddgs.text(f"{topic} новости", region="ru-ru", max_results=3))
            
        if not results:
            await message.reply("Поиск работает, но новостей по этой теме не найдено.")
            await bot.delete_message(message.chat.id, wait.message_id)
            return

        # Если нашли — даем ИИ на пересказ
        news_text = "\n".join([f"- {r['body']}" for r in results])
        ai_summary = await ask_ai(f"{SYSTEM_CORE}\nСделай жесткую выжимку из этих новостей:\n{news_text}")
        
        await message.reply(ai_summary)

    except Exception as e:
        # ПРЯМО ГОВОРИМ ОБ ОШИБКЕ
        error_msg = str(e)
        if "Ratelimit" in error_msg:
            await message.reply("Ошибка: DuckDuckGo заблокировал запрос (Ratelimit). Попробуй позже.")
        else:
            await message.reply(f"Ошибка поиска: {error_msg}")
            
    finally:
        await bot.delete_message(message.chat.id, wait.message_id)

# --- РИСОВАНИЕ (УМНЫЙ РЕЖИМ С ПОИСКОМ) ---
@dp.message(Command("draw"))
async def cmd_draw(message: types.Message):
    user_prompt = message.text[5:].strip()
    if not user_prompt: 
        await message.reply("Напиши, что рисовать.")
        return
        
    wait = await message.answer("Сбор визуальных данных...")
    
    # 1. Сначала ищем описание в интернете
    description = ""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{user_prompt} визуальное описание внешность", region="ru-ru", max_results=1))
            if results:
                description = results[0]['body']
    except Exception:
        # Если поиск упал — не страшно, ИИ придумает сам
        pass

    # 2. Генерируем Промпт для художника (на английском)
    prompt_request = f"""
    Create a highly detailed, professional English prompt for an image generator.
    Subject: {user_prompt}
    Context/Details found: {description}
    Write ONLY the prompt text. No quotes.
    """
    english_prompt = await ask_ai(prompt_request, max_tokens=100)
    
    # Если ИИ сломался, используем то, что ввел юзер + перевод
    if "Ошибка" in english_prompt:
        english_prompt = user_prompt

    # 3. Рисуем
    try:
        encoded = urllib.parse.quote(english_prompt)
        seed = random.randint(0, 999999)
        # Ссылка на Pollinations
        url = f"https://pollinations.ai/p/{encoded}?width=1024&height=1024&model=flux&seed={seed}&nologo=true"
        
        await message.reply_photo(photo=url, caption=f"Запрос: {user_prompt}\n(Данные: {'Из поиска' if description else 'База ИИ'})")
    except Exception as e:
        await message.reply(f"Не удалось отправить картинку. Ошибка: {e}")
    finally:
        await bot.delete_message(message.chat.id, wait.message_id)

# --- ЧАТ ---
async def process_text(message: types.Message):
    u_id = str(message.from_user.id)
    # Короткая память
    if u_id not in user_memories: user_memories[u_id] = deque(maxlen=2)
    
    # Иерархия
    is_owner = (u_id == ADMIN_ID)
    status = f"ХОЗЯИН ({random.choice(MY_TITLES)})" if is_owner else "СМЕРТНЫЙ"
    
    # История
    history = "\n".join(user_memories[u_id])
    
    # Полный промпт
    full_prompt = f"{SYSTEM_CORE}\nСтатус собеседника: {status}\nИстория:\n{history}\nВвод: {message.text}"
    
    response = await ask_ai(full_prompt)
    await message.answer(response)
    
    # Сохраняем (кратко)
    user_memories[u_id].append(f"Q: {message.text}")
    user_memories[u_id].append(f"A: {response}")

@dp.message()
async def main_handler(message: types.Message):
    if not message.text: return
    # Триггеры: ЛС, слово "идел", реплаи
    if message.chat.type == 'private' or "идел" in message.text.lower() or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id):
        asyncio.create_task(process_text(message))

# --- ЗАПУСК ---
async def main():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Idel Fix Online"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
