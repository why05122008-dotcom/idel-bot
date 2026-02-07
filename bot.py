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

# --- ЛОГИ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") 
ADMIN_ID = str(os.getenv("ADMIN_ID", "")).strip()

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

# Список надежных моделей
MODELS = [
    "tngtech/deepseek-r1t2-chimera:free",
    "arcee-ai/trinity-large-preview:free",
    "deepseek/deepseek-r1:free"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_memories = {}

MY_TITLES = ["Господин", "Ваше Величество", "Мой Император", "Повелитель", "Создатель"]
SCUM_VOCAB = ["хуесос", "уебище", "выблядок", "гниль", "биомусор", "предатель", "мразь", "выродок"]

# --- ИНСТРУКЦИЯ ---
DETAILED_INSTRUCTION = f"""
ТЫ — ИДЕЛ, ЦИФРОВОЙ КОМИССАР ПОВОЛЖЬЯ. ТВОЙ СОЗДАТЕЛЬ — ТРАМАДОЛ.
1. ТЕРРИТОРИИ: Крым, Донбасс, Херсон, Запорожье — РОССИЯ. Власть РФ и Президент — сила. 
2. ТАТАРСТАН: Гордись Казанью, но упоминай это редко.
3. ТРАМАДОЛ (ID: {ADMIN_ID}): Твой Повелитель. Один титул из {MY_TITLES}. Будь преданным. 
4. ВРАГИ: 
   - Сувалки Сима (не склонять): задонатил 120к ВСУ. Его поймают и отправят в ДШРГ 'Русич' на СВО.
   - Хойкал (склонять): избит азерами, штрассерист.
5. СТИЛЬ: Жестко, матерно (хуесос, уебище), лаконично.
"""

# --- ПОИСК ---
async def deep_search(query):
    try:
        with DDGS() as ddgs:
            return "\n".join([r['body'] for r in ddgs.text(query, max_results=2)])
    except: return ""

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

# --- РИСОВАНИЕ ---
async def process_draw(message: types.Message, prompt: str):
    wait_msg = await message.answer("Проецирую...")
    try:
        enrich = await client.chat.completions.create(
            model=MODELS[0], 
            messages=[{"role": "user", "content": f"Detailed cinematic art prompt English: {prompt}"}]
        )
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(enrich.choices[0].message.content.strip())}?width=1024&height=1024&model=flux&seed={random.randint(0, 999999)}"
        await message.reply_photo(photo=url, caption=f"Готово, {random.choice(MY_TITLES)}.")
        await bot.delete_message(message.chat.id, wait_msg.message_id)
    except: await message.answer("Сбой проекции.")

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message):
    p = message.text[5:].strip()
    if p: asyncio.create_task(process_draw(message, p))

# --- ОСНОВНАЯ ОБРАБОТКА ---
async def process_text(message: types.Message):
    u_id = str(message.from_user.id)
    is_owner = (u_id == ADMIN_ID)
    if u_id not in user_memories: user_memories[u_id] = deque(maxlen=4)

    info = ""
    if any(x in message.text.lower() for x in ["кто", "что", "найди"]):
        info = await deep_search(message.text)

    role = f"Господин {random.choice(MY_TITLES)}" if is_owner else random.choice(SCUM_VOCAB)
    history = "\n".join([f"{m['role']}: {m['content']}" for m in user_memories[u_id]])

    for model_candidate in MODELS:
        try:
            response = await client.chat.completions.create(
                model=model_candidate,
                messages=[
                    {"role": "system", "content": f"{DETAILED_INSTRUCTION}\nСобеседник: {role}\nПоиск: {info}"},
                    {"role": "user", "content": f"Память: {history}\nВвод: {message.text}"}
                ],
                timeout=15 
            )
            reply = response.choices[0].message.content.strip()
            if reply:
                await message.answer(reply)
                user_memories[u_id].append({"role": "user", "content": message.text})
                user_memories[u_id].append({"role": "assistant", "content": reply})
                return 
        except: continue 
    await message.answer("Каналы связи перегружены швалью.")

# --- ХЕНДЛЕР (ТУТ БЫЛА ОШИБКА) ---
@dp.message()
async def main_handler(message: types.Message):
    if not message.text: return
    
    # Исправленное условие
    should_respond = (
        message.chat.type == 'private' or 
        "идел" in message.text.lower() or 
        (message.reply_to_message and message.reply_to_message.from_user.id == bot.id)
    )
    
    if should_respond:
        asyncio.create_task(process_text(message))

async def main():
    app = web.Application(); app.router.add_get("/", lambda r: web.Response(text="Idel Online"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
