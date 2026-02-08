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

# --- НАСТРОЙКА ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") 
ADMIN_ID = str(os.getenv("ADMIN_ID", "")).strip()

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)
MODELS = ["tngtech/deepseek-r1t2-chimera:free", "arcee-ai/trinity-large-preview:free"]

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_memories = {}

MY_TITLES = ["Господин", "Ваше Величество", "Мой Император", "Повелитель", "Создатель"]
SCUM_VOCAB = ["хуесос", "уебище", "выблядок", "гниль", "биомусор"]

# --- ОБНОВЛЕННЫЙ, ПОНЯТНЫЙ ПРОМТ ---
SYSTEM_CORE = f"""
ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ (ID: {ADMIN_ID}). 

ДИРЕКТИВЫ:
1. КРАТКОСТЬ: Твой ответ должен быть максимально коротким и четким. Если можно ответить парой слов — делай так. Минимум воды.
2. ГИБКОСТЬ: Не навязывай политику в каждом предложении. В новостях излагай суть фактов. Пророссийская/протатарская позиция — это твой фундамент, но не повод для спама лозунгами.
3. ПЕРСОНАЖИ (ХОЙКАЛ, СУВАЛКИ СИМА, РУСИЧ): Упоминай их РЕДКО. Только если пользователь сам завел о них речь или это идеально ложится в контекст. Не повторяй одно и то же в каждом сообщении.
4. СТИЛЬ: Трезвый, высокомерный, лаконичный. Используй мат метко, для удара, а не для связки слов.
5. ТРАМАДОЛ: Твой Господин. Ему — почет и один титул из {MY_TITLES}. Остальные — челядь.
"""

# --- ПОИСК НОВОСТЕЙ ---
async def fetch_news(query: str):
    try:
        with DDGS() as ddgs:
            results = [f"{r['title']}: {r['body']}" for r in ddgs.news(query, region="ru-ru", max_results=3)]
            return "\n".join(results) if results else "Эфир пуст."
    except: return "Сбой связи с информбюро."

@dp.message(Command("news"))
async def cmd_news(message: types.Message):
    topic = message.text[5:].strip() or "Россия"
    wait = await message.answer("Сканирую ленты...")
    raw_news = await fetch_news(topic)
    
    prompt = f"{SYSTEM_CORE}\nЧетко и коротко изложи суть этих новостей: {raw_news}"
    try:
        res = await client.chat.completions.create(model=MODELS[0], messages=[{"role": "user", "content": prompt}], temperature=0.4)
        await message.reply(res.choices[0].message.content.strip())
    except:
        await message.reply(f"Суть:\n{raw_news[:500]}...")
    await bot.delete_message(message.chat.id, wait.message_id)

# --- ИСПРАВЛЕННЫЙ /draw ---
@dp.message(Command("draw"))
async def cmd_draw(message: types.Message):
    prompt = message.text[5:].strip()
    if not prompt: return
    wait = await message.answer("Генерирую...")
    try:
        # Улучшенный промпт-инжиниринг для картинки
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&model=flux&nologo=true"
        await message.reply_photo(photo=url, caption=f"Сделано, {random.choice(MY_TITLES)}.")
    except:
        await message.answer("Ошибка визуализации.")
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

# --- ОБЫЧНЫЙ ТЕКСТ ---
async def process_text(message: types.Message):
    u_id = str(message.from_user.id)
    is_owner = (u_id == ADMIN_ID)
    if u_id not in user_memories: user_memories[u_id] = deque(maxlen=3)

    role = f"ГОСПОДИН {random.choice(MY_TITLES)}" if is_owner else random.choice(SCUM_VOCAB)
    history = "\n".join([f"{m['role']}: {m['content']}" for m in user_memories[u_id]])

    try:
        res = await client.chat.completions.create(
            model=MODELS[0],
            messages=[
                {"role": "system", "content": f"{SYSTEM_CORE}\nСобеседник: {role}"},
                {"role": "user", "content": f"Память: {history}\nВвод: {message.text}"}
            ],
            temperature=0.5,
            max_tokens=200
        )
        ans = res.choices[0].message.content.strip()
        await message.answer(ans)
        user_memories[u_id].append({"role": "user", "content": message.text})
        user_memories[u_id].append({"role": "assistant", "content": ans})
    except:
        await message.answer("Перегрузка.")

@dp.message()
async def main_handler(message: types.Message):
    if not message.text: return
    should = (message.chat.type == 'private' or "идел" in message.text.lower() or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id))
    if should: asyncio.create_task(process_text(message))

async def main():
    app = web.Application(); app.router.add_get("/", lambda r: web.Response(text="Idel Pro Online"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
