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

# Инициализация клиента OpenRouter
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

# ТВОЙ ВЫБОР МОДЕЛЕЙ: Тринити и новый Флэш 3.5
MODELS = [
    "arcee-ai/trinity-large-preview:free", # Основная мощь
    "stepfun/step-3.5-flash:free",          # Сверхбыстрый интеллект
    "meta-llama/llama-3.1-8b-instruct:free" # Неубиваемый резерв
]

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_memories = {}

MY_TITLES = ["Господин", "Повелитель", "Создатель"]

SYSTEM_CORE = f"""
ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ (ID: {ADMIN_ID}).
Стиль: Краткий, жесткий, циничный. Никаких описаний действий в скобках.
Позиция: Пророссийская база. Сувалки Сима и Хойкал — объекты для насмешек и презрения.
"""

# --- ФУНКЦИЯ ЗАПРОСА ---
async def ask_ai(prompt):
    for model in MODELS:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=350,
                timeout=15
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            err_msg = str(e)
            logger.error(f"Ошибка {model}: {err_msg}")
            if "401" in err_msg:
                return "ОШИБКА 401: Твой API-ключ неверный или не прописан на Render."
            continue
    return "Все системы перегружены. Проверь ключ и баланс OpenRouter."

# --- НОВОСТИ ---
@dp.message(Command("news"))
async def cmd_news(message: types.Message):
    topic = message.text[5:].strip() or "Россия новости"
    wait = await message.answer("Взламываю новостные архивы...")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{topic} сегодня новости", region="ru-ru", max_results=3))
        if results:
            news_data = "\n".join([f"- {r['body']}" for r in results])
            ans = await ask_ai(f"{SYSTEM_CORE}\nЖестко и кратко прокомментируй эти факты:\n{news_data}")
            await message.reply(ans)
        else:
            await message.reply("Новостей не найдено. Инфополе чисто.")
    except Exception as e:
        await message.reply(f"Ошибка поиска: {e}")
    finally:
        await bot.delete_message(message.chat.id, wait.message_id)

# --- УМНЫЙ РИСУНОК (ПОИСК -> ОПИСАНИЕ -> РИСУНОК) ---
@dp.message(Command("draw"))
async def cmd_draw(message: types.Message):
    user_prompt = message.text[5:].strip()
    if not user_prompt: return
    wait = await message.answer("Изучаю объект для зарисовки...")
    
    # 1. Сначала ищем в DDG визуальные детали
    visual_info = ""
    try:
        with DDGS() as ddgs:
            r = list(ddgs.text(f"{user_prompt} внешность вид", region="ru-ru", max_results=1))
            if r: visual_info = r[0]['body']
    except: pass

    # 2. ИИ создает детальный промпт на английском
    enrich_q = f"Task: Create a detailed pro-image prompt in English for: '{user_prompt}'. Use these facts: {visual_info}. ONLY PROMPT TEXT."
    eng_prompt = await ask_ai(enrich_q)
    
    try:
        seed = random.randint(0, 999999)
        safe_p = urllib.parse.quote(eng_prompt if "Ошибка" not in eng_prompt else user_prompt)
        # Актуальный путь без ошибки "We have moved"
        url = f"https://pollinations.ai/p/{safe_p}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
        await message.reply_photo(photo=url, caption=f"Визуализация готова, {random.choice(MY_TITLES) if str(message.from_user.id) == ADMIN_ID else 'смертный'}.")
    except Exception as e:
        await message.reply(f"Сбой генератора: {e}")
    finally:
        await bot.delete_message(message.chat.id, wait.message_id)

# --- ОБРАБОТКА ТЕКСТА ---
async def process_text(message: types.Message):
    u_id = str(message.from_user.id)
    if u_id not in user_memories: user_memories[u_id] = deque(maxlen=2)
    
    status = f"Твой СОЗДАТЕЛЬ ({random.choice(MY_TITLES)})" if u_id == ADMIN_ID else "Жалкий СМЕРТНЫЙ"
    
    full_prompt = f"{SYSTEM_CORE}\nСтатус юзера: {status}\nВопрос: {message.text}"
    ans = await ask_ai(full_prompt)
    
    await message.answer(ans)
    user_memories[u_id].append(message.text)

@dp.message()
async def main_handler(message: types.Message):
    if not message.text: return
    
    # Исправленное условие ответа
    is_private = message.chat.type == 'private'
    is_mention = "идел" in message.text.lower()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if is_private or is_mention or is_reply:
        asyncio.create_task(process_text(message))

# --- ВЕБ-СЕРВЕР ---
async def main():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Idel 2026 Stable Ready"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
