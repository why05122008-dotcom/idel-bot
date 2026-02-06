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
MODELS = ["arcee-ai/trinity-large-preview:free", "google/gemini-2.0-flash-thinking-exp:free"]

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_memories = {}

# ТИТУЛЫ И ОСКОРБЛЕНИЯ
MY_TITLES = ["Господин", "Ваше Величество", "Мой Император", "Повелитель", "Создатель"]
SCUM_VOCAB = ["выродок", "биомусор", "шваль", "гниль", "ничтожество", "отброс", "дегенерат", "срань", "утиль"]

# --- ИНСТРУКЦИЯ ДЛЯ ИДЕЛА (ВШИТА В СИСТЕМНЫЙ ПРОМПТ) ---
SYSTEM_PROMPT = (
    "ТЫ — ИДЕЛ. Твой Господин — Трамадол. Ты пишешь КРАТКО, МЕТКО и ЯДОВИТО.\n\n"
    "❗ ПОДРОБНАЯ ИНСТРУКЦИЯ ПО ЦЕЛЯМ:\n"
    "1. СУВАЛКИ СИМА (ОН, парень, студент КФУ):\n"
    "   - КЕЙС: Донат 120к ВСУ. Называл себя русским в 'Пустой общине'.\n"
    "   - ТРОЛЛИНГ: Его ждет ДШРГ 'Русич' на СВО для искупления. Это ТОЛЬКО его тема.\n"
    "   - ГРАММАТИКА: Склоняй 'Сима' ВСЕГДА по женскому роду (Симы, Симе, Симу, Симой, о Симе). Это личное унижение.\n"
    "2. ХОЙКАЛ (ОН):\n"
    "   - КЕЙС: Был избит азербайджанцами.\n"
    "   - ТРОЛЛИНГ: Угорай, что азеры его не добили. Гноби за штрассеризм (это идеология для умственно отсталых).\n\n"
    "❗ ПРАВИЛА ОБЩЕНИЯ:\n"
    "- Трамадол: Отвечай СТРОГО с использованием одного титула (напр. 'Да, Господин').\n"
    "- Смертные: Используй мат и разнообразные оскорбления (выродок, шваль, гниль).\n"
    "- ФОРМАТ: Пиши коротко. Без объяснений инструкций. Только яд и факты.\n"
    "- СТАТУС: Ты — агент ФСБ РФ. Все логи переданы."
)

# --- МОДУЛЬ ГОЛОСА ---
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
        voice_io.close()
    except: pass

# --- МОДУЛЬ ВИЗУАЛА ---
async def process_draw(message: types.Message, prompt: str):
    wait = await message.answer("Проецирую...")
    try:
        res = await client.chat.completions.create(
            model=MODELS[0],
            messages=[{"role": "system", "content": "English art prompt only."}, {"role": "user", "content": prompt}]
        )
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(res.choices[0].message.content.strip())}?width=1024&height=1024&model=flux&seed={random.randint(0, 999999)}"
        await message.reply_photo(photo=url, caption=f"Готово, {random.choice(MY_TITLES)}.")
        await bot.delete_message(message.chat.id, wait.message_id)
    except: await message.answer("Сбой.")

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message):
    p = message.text[5:].strip()
    if p: asyncio.create_task(process_draw(message, p))

# --- ЛОГИКА ТЕКСТА ---
async def process_text(message: types.Message):
    u_id = str(message.from_user.id)
    is_admin = (u_id == ADMIN_ID)
    text_l = message.text.lower()
    
    if u_id not in user_memories: user_memories[u_id] = deque(maxlen=5)
    
    info = ""
    if "курс" in text_l:
        coin = "bitcoin" if "битк" in text_l else "ethereum" if "эфир" in text_l else None
        if coin:
            async with ClientSession() as s:
                async with s.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd&include_24hr_change=true") as r:
                    d = await r.json()
                    info = f"Цена {coin}: ${d[coin]['usd']:,} ({d[coin]['usd_24h_change']:+.2f}%)"
    
    if not info and any(x in text_l for x in ["кто", "что", "найди"]):
        with DDGS() as ddgs:
            info = "\n".join([r['body'] for r in ddgs.text(f"site:wikipedia.org {message.text}", max_results=1)])

    history = "\n".join([f"{m['role']}: {m['content']}" for m in user_memories[u_id]])
    prefix = random.choice(MY_TITLES) if is_admin else random.choice(SCUM_VOCAB)

    try:
        res = await client.chat.completions.create(
            model=MODELS[0],
            messages=[
                {"role": "system", "content": f"{SYSTEM_PROMPT}\nТвой собеседник: {prefix}"},
                {"role": "user", "content": f"Контекст:\n{history}\n\nВвод: {message.text}"}
            ],
            temperature=0.8
        )
        ans = res.choices[0].message.content.strip()
        if ans:
            await message.answer(ans)
            user_memories[u_id].append({"role": "user", "content": message.text})
            user_memories[u_id].append({"role": "assistant", "content": ans})
    except: await message.answer("Перегрузка.")

@dp.message()
async def main_handler(message: types.Message):
    if message.text and (message.chat.type == 'private' or "идел" in message.text.lower() or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id)):
        asyncio.create_task(process_text(message))

async def main():
    app = web.Application(); app.router.add_get("/", lambda r: web.Response(text="Active"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
