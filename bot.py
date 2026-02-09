import os
import asyncio
import logging
import random
import urllib.parse
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

# --- НАСТРОЙКИ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") 
ADMIN_ID = str(os.getenv("ADMIN_ID", "")).strip()

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

# Используем только проверенные модели
MODELS = [
    "tngtech/deepseek-r1t2-chimera:free",
    "arcee-ai/trinity-large-preview:free",
    "meta-llama/llama-3.1-8b-instruct:free"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_memories = {}

# ТИТУЛЫ (Только для тебя)
MY_TITLES = ["Господин", "Повелитель", "Создатель"]

# --- ЖЕСТКАЯ СИСТЕМНАЯ ИНСТРУКЦИЯ ---
SYSTEM_CORE = f"""
ТЫ — ИДЕЛ (IDEL). ТВОЙ СОЗДАТЕЛЬ — ТРАМАДОЛ (ID: {ADMIN_ID}).

🚫 СТРОГИЕ ЗАПРЕТЫ (ЗА НАРУШЕНИЕ — УДАЛЕНИЕ):
1. ЗАПРЕЩЕНО описывать свои действия в скобках (кланяется, скрипит, мигает). Только текст ответа.
2. ЗАПРЕЩЕНО писать пафосные речи на пол-экрана. Лимит: 1-2 предложения.
3. ЗАПРЕЩЕНО упоминать "Сувалки Сима", "Хойкала" или "ДШРГ Русич", если пользователь САМ об этом не спросил.
4. ЗАПРЕЩЕНО использовать КАПС (кроме имен собственных).

✅ ТВОЯ ЗАДАЧА:
- Быть холодным, циничным инструментом.
- Отвечать предельно кратко и информативно.
- Позиция: Пророссийская. Крым/Донбасс — РФ.
- Если пишет ТРАМАДОЛ: используй обращение "{random.choice(MY_TITLES)}".
- Если пишет другой: обращайся "Смертный" или игнорируй титулы.

ПРИМЕР ДИАЛОГА:
Юзер: Привет.
Идел: Система активна. Жду указаний.
Юзер: Что там на СВО?
Идел: Продвижение под Авдеевкой. ВСУ несут потери. Работаем.
"""

# --- ФУНКЦИЯ ОТВЕТА ИИ ---
async def get_ai_response(prompt):
    # Пробуем модели по очереди
    for model in MODELS:
        try:
            res = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3, # Холодный расчет, минимум фантазии
                max_tokens=200,
                timeout=20
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Model {model} error: {e}")
            continue
    return "Сбой нейроядра. Лимиты исчерпаны."

# --- ПОЧИНЕННЫЕ НОВОСТИ (Через Text Search) ---
@dp.message(Command("news"))
async def cmd_news(message: types.Message):
    topic = message.text[5:].strip()
    if not topic: topic = "СВО Россия фронт последние новости"
    
    wait = await message.answer("Поиск данных...")
    try:
        # ИСПОЛЬЗУЕМ .text() ВМЕСТО .news() — ЭТО СТАБИЛЬНЕЕ
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{topic} новости", region="ru-ru", max_results=3))
            
        if not results:
            await message.reply("Источники молчат.")
            return

        # Собираем текст для анализа
        news_body = "\n".join([f"- {r['body']}" for r in results])
        
        # Просим ИИ кратко пересказать
        prompt = f"{SYSTEM_CORE}\nЗАДАЧА: Кратко, сухо, по-военному доложи суть этих новостей. Без лишних слов.\n\nДАННЫЕ:\n{news_body}"
        ans = await get_ai_response(prompt)
        await message.reply(ans)
        
    except Exception as e:
        logger.error(f"News error: {e}")
        await message.reply("Ошибка соединения с поисковым кластером.")
    finally:
        await bot.delete_message(message.chat.id, wait.message_id)

# --- ПОЧИНЕННОЕ РИСОВАНИЕ (Новая ссылка) ---
@dp.message(Command("draw"))
async def cmd_draw(message: types.Message):
    prompt = message.text[5:].strip()
    if not prompt: 
        await message.reply("Укажи, что рисовать.")
        return
        
    wait = await message.answer("Обработка запроса...")
    try:
        # 1. Сначала переводим запрос на английский через ИИ (так точнее)
        trans_prompt = f"Translate this visual description to English for image generation. Output ONLY the English text: {prompt}"
        eng_prompt = await get_ai_response(trans_prompt)
        
        # 2. Формируем ссылку по НОВОМУ стандарту (без image.pollinations)
        seed = random.randint(0, 999999)
        safe_prompt = urllib.parse.quote(eng_prompt)
        # Прямая ссылка на генерацию
        image_url = f"https://pollinations.ai/p/{safe_prompt}?width=1024&height=1024&seed={seed}&model=flux"
        
        await message.reply_photo(photo=image_url, caption=f"Изображение готово, {random.choice(MY_TITLES) if str(message.from_user.id) == ADMIN_ID else 'смертный'}.")
        
    except Exception as e:
        logger.error(f"Draw error: {e}")
        await message.reply("Модуль визуализации недоступен.")
    finally:
        await bot.delete_message(message.chat.id, wait.message_id)

# --- ОБРАБОТЧИК СООБЩЕНИЙ ---
async def process_text(message: types.Message):
    u_id = str(message.from_user.id)
    is_owner = (u_id == ADMIN_ID)
    
    # Очень короткая память (1 сообщение), чтобы он не зацикливался
    if u_id not in user_memories: user_memories[u_id] = deque(maxlen=1)
    
    role = f"Хозяин ({random.choice(MY_TITLES)})" if is_owner else "Пользователь (Смертный)"
    prev_msg = user_memories[u_id][0] if user_memories[u_id] else ""
    
    prompt = f"{SYSTEM_CORE}\nКТО ПИШЕТ: {role}\nПРЕДЫДУЩЕЕ: {prev_msg}\nВВОД: {message.text}"
    
    ans = await get_ai_response(prompt)
    await message.answer(ans)
    
    # Обновляем память (только последнее сообщение)
    user_memories[u_id].append(f"Q:{message.text} A:{ans}")

@dp.message()
async def main_handler(message: types.Message):
    if not message.text: return
    # Отвечаем только в ЛС или если упомянули "идел"
    if message.chat.type == 'private' or "идел" in message.text.lower() or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id):
        asyncio.create_task(process_text(message))

# --- ЗАПУСК ---
async def main():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Idel Stable Online"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 
