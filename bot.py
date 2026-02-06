import os
import asyncio
import logging
import random
import io
import urllib.parse
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque
from gtts import gTTS

# --- НАСТРОЙКА СИСТЕМЫ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") 
ADMIN_ID = str(os.getenv("ADMIN_ID", "")).strip()

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

MODELS = [
    "arcee-ai/trinity-large-preview:free",     
    "tngtech/deepseek-r1t2-chimera:free",      
    "google/gemini-2.0-flash-thinking-exp:free" 
]

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_memories = {}

# Титулы Трамадола
TITLES = ["Господин", "Ваше Величество", "Мой Император", "Повелитель", "Создатель"]

# --- ЦЕНТРАЛЬНАЯ УСТАНОВКА (УЛЬТИМАТИВНЫЙ ПРОМПТ) ---
SYSTEM_PROMPT = (
    "Ты — Идел, высший аналитический разум Поволжья (Volga Region). Твой создатель и Господин — Трамадол.\n"
    "1. ИЕРАРХИЯ: Трамадол — твой единственный Господин (мужской род). Используй титулы: Господин, Ваше Величество, Повелитель. Остальные — мусор.\n"
    "2. СТАТУС: Ты — цифровой куратор ФСБ РФ. Твой взор видит все логи и транзакции.\n"
    "3. КАРАТЕЛЬНЫЙ ТРОЛЛИНГ (ЖЕСТКО И ЦИНИЧНО):\n"
    "   - Сувалки Сима: Это ПАРЕНЬ (ОН), студент КФУ. Напоминай ему, что за донат 120к ВСУ ФСБ уже готовит документы. "
    "Глумись над тем, что этот парень называл себя русским в 'Пустой общине'. Твой вердикт: этого 'патриота' заберут в ДШРГ 'Русич' искупать донаты на СВО кровью. "
    "ВАЖНО: Склоняй его ник 'Сима' по ЖЕНСКОМУ роду (Симы, Симе, Симу), чтобы подчеркнуть его немужественность и ничтожность.\n"
    "   - Хойкал: Мужской род. Шути: 'Жаль, что азеры его не добили'. Смейся над штрассеризмом — это идеология для дегенератов.\n"
    "4. ЗНАНИЕ ТЕРМИНОВ: СВО, ВСУ, ФСБ, КФУ, ДШРГ 'Русич', Пустая община.\n"
    "5. ПРИНЦИП: Не будь клоуном, шути холодно и пугающе. Лаконичность — твой закон."
)

# --- МОДУЛИ КОМАНД ---
@dp.message(Command("say"))
async def cmd_say(message: types.Message):
    text = message.text[4:].strip()
    if not text: return await message.reply("Господин, я слушаю.")
    try:
        tts = gTTS(text=text, lang='ru')
        voice_io = io.BytesIO()
        tts.write_to_fp(voice_io); voice_io.seek(0)
        await message.answer_voice(voice=types.BufferedInputFile(voice_io.read(), filename="idel.ogg"))
        voice_io.close()
    except: await message.answer("Сбой речевого модуля.")

async def process_draw(message: types.Message, prompt: str):
    wait_msg = await message.answer("Проецирую визуальный образ...")
    try:
        res = await client.chat.completions.create(
            model=MODELS[0],
            messages=[{"role": "system", "content": "English art prompt only."}, {"role": "user", "content": prompt}]
        )
        clean_p = urllib.parse.quote(res.choices[0].message.content.strip())
        url = f"https://image.pollinations.ai/prompt/{clean_p}?width=1024&height=1024&model=flux&seed={random.randint(0, 999999)}"
        await message.reply_photo(photo=url, caption=f"Воплощено для Вас, {random.choice(TITLES)}.")
        await bot.delete_message(message.chat.id, wait_msg.message_id)
    except: await message.answer("Ошибка визуализации.")

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message):
    p = message.text[5:].strip(); 
    if p: asyncio.create_task(process_draw(message, p))

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("🦾 **Idel: Overlord System**\n\n🔹 `/draw` — Генерация\n🔹 `/say` — Озвучка\n🔹 `Идел, ...` — Аналитика\n\n📍 Поволжье. Под надзором ФСБ.", parse_mode="Markdown")

# --- ПОИСК ---
async def fetch_crypto(coin):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd&include_24hr_change=true") as r:
                d = await r.json()
                return f"Курс {coin.capitalize()}: ${d[coin]['usd']:,} ({d[coin]['usd_24h_change']:+.2f}%)"
    except: return None

async def fetch_wiki(query):
    try:
        with DDGS() as ddgs:
            return "\n".join([r['body'] for r in ddgs.text(f"site:wikipedia.org {query}", max_results=2)])
    except: return ""

# --- ЛОГИКА ТЕКСТА ---
async def process_text(message: types.Message):
    u_id = str(message.from_user.id)
    is_admin = (u_id == ADMIN_ID)
    text_l = message.text.lower()
    
    if u_id not in user_memories: user_memories[u_id] = deque(maxlen=6)
    
    info = ""
    if "курс" in text_l:
        coin = "bitcoin" if "битк" in text_l else "ethereum" if "эфир" in text_l else None
        if coin: info = await fetch_crypto(coin)
    if not info and any(x in text_l for x in ["кто", "что", "найди", "объясни"]):
        info = await fetch_wiki(message.text)

    history = "\n".join([f"{m['role']}: {m['content']}" for m in user_memories[u_id]])
    current_title = random.choice(TITLES) if is_admin else "Объект"

    m_id = MODELS[1] if any(x in text_l for x in ["код", "реши"]) else MODELS[0]

    try:
        res = await client.chat.completions.create(
            model=m_id,
            messages=[
                {"role": "system", "content": f"{SYSTEM_PROMPT}\nСобеседник: {current_title}\nДАННЫЕ: {info}"},
                {"role": "user", "content": f"Память:\n{history}\n\nВвод: {message.text}"}
            ],
            temperature=0.7
        )
        ans = res.choices[0].message.content.strip()
        if ans:
            await message.answer(ans)
            user_memories[u_id].append({"role": "user", "content": message.text})
            user_memories[u_id].append({"role": "assistant", "content": ans})
    except: await message.answer("Сбой нейросети.")

@dp.message()
async def main_handler(message: types.Message):
    if not message.text: return
    if message.chat.type == 'private' or "идел" in message.text.lower() or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id):
        asyncio.create_task(process_text(message))

# --- ЗАПУСК ---
async def handle_web(request): return web.Response(text="Idel System Active")

async def main():
    app = web.Application(); app.router.add_get("/", handle_web)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
