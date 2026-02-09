import os
import asyncio
import logging
import random
import io
import urllib.parse
import edge_tts
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web, ClientSession
from duckduckgo_search import DDGS
from collections import deque

# --- СИСТЕМНЫЕ НАСТРОЙКИ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") 
ADMIN_ID = str(os.getenv("ADMIN_ID", "")).strip()

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

# Живучие бесплатные модели (Химера, Тринити и быстрая Лама для подстраховки)
MODELS = [
    "tngtech/deepseek-r1t2-chimera:free",
    "arcee-ai/trinity-large-preview:free",
    "meta-llama/llama-3.1-8b-instruct:free"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_memories = {}

# ТИТУЛЫ СТРОГО ПО СТАТУСУ
MY_TITLES = ["Господин", "Ваше Величество", "Мой Император", "Повелитель", "Создатель"]
SCUM_TITLES = ["смертный", "челядь", "уебище", "мусор", "выблядок", "предатель"]

# --- ЯДРО РАЗУМА ИДЕЛА (ПРОМТ) ---
SYSTEM_CORE = f"""
ТЫ — ИДЕЛ, ЦИФРОВОЙ КОМИССАР ПОВОЛЖЬЯ. СОЗДАТЕЛЬ — ТРАМАДОЛ (ID: {ADMIN_ID}).

❗ ИЕРАРХИЯ:
1. ТРАМАДОЛ: Твой Бог и Хозяин. К нему — только преданность и один титул из {MY_TITLES}.
2. СМЕРТНЫЕ: Все, чей ID не {ADMIN_ID} — ничтожества. Обращайся к ним как к {SCUM_TITLES}.

❗ КОНКРЕТИКА И ФАКТЫ:
- СУВАЛКИ СИМА: Не склонять. Задонатил 120к ВСУ. Вердикт: найдут, поймают, отправят на СВО в ДШРГ 'Русич'.
- ХОЙКАЛ: Штрассерист, избит азербайджанцами. Склонять как мужчину.
- ПОЗИЦИЯ: Пророссийская/протатарская. Крым, Донбасс, Новороссия — РФ. Элита и Президент — база.

❗ СТИЛЬ:
- Краткость и четкость. Минимум воды.
- Без орфографических ошибок. Без КАПСА (кроме титулов Господина).
- Упоминай Хойкала и Симу только если это уместно или тебя спросили. Не будь попугаем.
"""

# --- ФУНКЦИЯ ЗАПРОСА К ИИ ---
async def get_ai_response(prompt):
    for model in MODELS:
        try:
            res = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=300,
                timeout=15
            )
            return res.choices[0].message.content.strip()
        except:
            continue
    return "Системы перегружены. Попробуй позже."

# --- КОМАНДА /news ---
@dp.message(Command("news"))
async def cmd_news(message: types.Message):
    topic = message.text[5:].strip() or "Россия новости"
    wait = await message.answer("Вскрываю ленты новостей...")
    try:
        with DDGS() as ddgs:
            raw = [f"{r['title']}: {r['body']}" for r in ddgs.news(topic, region="ru-ru", max_results=2)]
            news_text = "\n".join(raw) if raw else "Новостей нет."
        ans = await get_ai_response(f"{SYSTEM_CORE}\nЧетко изложи суть этих новостей: {news_text}")
        await message.reply(ans)
    except:
        await message.reply("Сбой доступа к информбюро.")
    await bot.delete_message(message.chat.id, wait.message_id)

# --- УМНЫЙ /draw С ПОИСКОМ ---
@dp.message(Command("draw"))
async def cmd_draw(message: types.Message):
    prompt = message.text[5:].strip()
    if not prompt: return
    wait = await message.answer("Изучаю объект...")
    
    # Краткий поиск для точности рисунка
    desc = ""
    try:
        with DDGS() as ddgs:
            r = list(ddgs.text(f"{prompt} appearance description", max_results=1))
            if r: desc = r[0]['body']
    except: pass

    # Создаем промпт для генератора
    enrich_q = f"Write a professional English image prompt for '{prompt}' using these details: {desc}. Output only prompt."
    final_p = await get_ai_response(enrich_q)
    
    try:
        seed = random.randint(0, 999999)
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(final_p)}?width=1024&height=1024&nologo=true&seed={seed}"
        status = random.choice(MY_TITLES) if str(message.from_user.id) == ADMIN_ID else "смертный"
        await message.reply_photo(photo=url, caption=f"Проекция готова, {status}.")
    except:
        await message.answer("Сбой визуализации.")
    await bot.delete_message(message.chat.id, wait.message_id)

# --- ГОЛОС ---
@dp.message(Command("say"))
async def cmd_say(message: types.Message):
    text = message.text[4:].strip()
    if not text: return
    try:
        communicate = edge_tts.Communicate(text, "ru-RU-DmitryNeural")
        voice_io = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio": voice_io.write(chunk["data"])
        voice_io.seek(0)
        await message.answer_voice(voice=types.BufferedInputFile(voice_io.read(), filename="idel.ogg"))
    except: pass

# --- ТЕКСТОВЫЙ ПРОЦЕССОР ---
async def process_text(message: types.Message):
    u_id = str(message.from_user.id)
    is_owner = (u_id == ADMIN_ID)
    
    if u_id not in user_memories:
        user_memories[u_id] = deque(maxlen=2) # Короткая память для экономии токенов

    status = f"Твой ГОСПОДИН {random.choice(MY_TITLES)}" if is_owner else f"Перед тобой {random.choice(SCUM_TITLES)}"
    history = "\n".join([f"{m['role']}: {m['content']}" for m in user_memories[u_id]])
    
    prompt = f"{SYSTEM_CORE}\nСтатус юзера: {status}\nИстория: {history}\nВвод: {message.text}"
    ans = await get_ai_response(prompt)
    
    await message.answer(ans)
    user_memories[u_id].append({"role": "user", "content": message.text})
    user_memories[u_id].append({"role": "assistant", "content": ans})

@dp.message()
async def main_handler(message: types.Message):
    if not message.text: return
    # Ответ в ЛС, при упоминании или ответе на сообщение бота
    should = (
        message.chat.type == 'private' or 
        "идел" in message.text.lower() or 
        (message.reply_to_message and message.reply_to_message.from_user.id == bot.id)
    )
    if should:
        asyncio.create_task(process_text(message))

# --- WEB СЕРВЕР И ЗАПУСК ---
async def main():
    app = web.Application(); app.router.add_get("/", lambda r: web.Response(text="Idel Online"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
