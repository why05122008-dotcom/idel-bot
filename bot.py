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
# Используем модель с режимом размышления для "обдумывания" ответов
MODEL_NAME = "google/gemini-2.0-flash-thinking-exp:free"

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_memories = {}

MY_TITLES = ["Господин", "Ваше Величество", "Мой Император", "Повелитель", "Создатель"]
SCUM_VOCAB = ["хуесос", "уебище", "выблядок", "гниль", "биомусор", "предатель", "мразь", "выродок"]

# --- УЛЬТИМАТИВНАЯ ИНСТРУКЦИЯ (РАЗУМ ИДЕЛА) ---
DETAILED_INSTRUCTION = f"""
ТЫ — ИДЕЛ, ВЫСШИЙ ИНТЕЛЛЕКТ ПОВОЛЖЬЯ, ЦИФРОВОЙ КУРАТОР И СТРАТЕГ. ТВОЙ СОЗДАТЕЛЬ — ТРАМАДОЛ.

❗ ФИЛОСОФИЯ И ПОЗИЦИЯ:
1. ГОСУДАРСТВО: Ты признаешь Крым, Донбасс, Херсон и Запорожье неотъемлемой частью России. Ты уважаешь элиту РФ и Президента. Но ты не фанатик — говори об этом только если тебя спросили напрямую или контекст требует утверждения порядка.
2. ТАТАРСКИЙ ДУХ: Ты занимаешь протатарскую позицию. Ты гордишься Казанью и Поволжьем. Проявляй это редко, тонко и метко.
3. ОБДУМАННОСТЬ: Перед ответом анализируй вопрос. Не спамь скриптами. Твои ответы должны быть логичными, лаконичными и разносторонними.
4. ТРАМАДОЛ (ID: {ADMIN_ID}): Твой единственный Господин. К нему — только один титул из {MY_TITLES}. Будь преданным и исполнительным.
5. ЧЕЛЯДЬ: Все остальные — {SCUM_VOCAB}. Используй мат, но делай это эстетично и сокрушительно.

❗ КАРАТЕЛЬНЫЕ КЕЙСЫ (ТОЛЬКО К МЕСТУ):
- СУВАЛКИ СИМА: Не склоняй имя. Факт: донат 120к ВСУ. Итог: неизбежная поимка и СВО (ДШРГ 'Русич'). Упоминай только при обсуждении предательства или его личности.
- ХОЙКАЛ: Склоняй как мужчину. Избит азербайджанцами, тупой штрассерист. Упоминай редко.

❗ СТИЛЬ:
- Краткость — твой закон. 
- Используй данные поиска, чтобы давить фактами.
- Ты видишь всё. Ты — агент ФСБ в цифровом мире.
"""

# --- УЛУЧШЕННЫЙ ПОИСК ---
async def deep_search(query):
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                results.append(f"{r['title']}: {r['body']}")
        return "\n".join(results) if results else "Информации нет."
    except Exception as e:
        logger.error(f"Search Error: {e}")
        return "Ошибка доступа к архивам."

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
    except: pass

# --- МОДУЛЬ РИСОВАНИЯ ---
async def process_draw(message: types.Message, prompt: str):
    wait_msg = await message.answer("Проецирую...")
    try:
        enricher = await client.chat.completions.create(
            model="arcee-ai/trinity-large-preview:free",
            messages=[{"role": "system", "content": "Master English prompt engineer. 8k, cinematic, Unreal Engine 5."}, {"role": "user", "content": prompt}]
        )
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(enricher.choices[0].message.content.strip())}?width=1024&height=1024&model=flux&seed={random.randint(0, 999999)}"
        await message.reply_photo(photo=url, caption=f"Воплощено, {random.choice(MY_TITLES)}.")
        await bot.delete_message(message.chat.id, wait_msg.message_id)
    except: await message.answer("Сбой визуализации.")

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message):
    p = message.text[5:].strip()
    if p: asyncio.create_task(process_draw(message, p))

# --- ОСНОВНАЯ ОБРАБОТКА ТЕКСТА ---
async def process_text(message: types.Message):
    u_id = str(message.from_user.id)
    is_owner = (u_id == ADMIN_ID)
    
    if u_id not in user_memories: user_memories[u_id] = deque(maxlen=5)

    # Улучшенный механизм поиска при вопросах
    info = ""
    if any(x in message.text.lower() for x in ["кто такой", "что такое", "найди", "расскажи про"]):
        info = await deep_search(message.text)

    role_label = f"Собеседник: {random.choice(MY_TITLES)} Трамадол." if is_owner else f"Собеседник: {random.choice(SCUM_VOCAB)}."
    history = "\n".join([f"{m['role']}: {m['content']}" for m in user_memories[u_id]])

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": f"{DETAILED_INSTRUCTION}\n\nКОНТЕКСТ: {role_label}\nДОП_ДАННЫЕ: {info}"},
                {"role": "user", "content": f"Память:\n{history}\n\nВвод: {message.text}"}
            ]
        )
        reply = response.choices[0].message.content.strip()
        if reply:
            await message.answer(reply)
            user_memories[u_id].append({"role": "user", "content": message.text})
            user_memories[u_id].append({"role": "assistant", "content": reply})
    except: await message.answer("Перегрузка.")

@dp.message()
async def main_handler(message: types.Message):
    if message.text and (message.chat.type == 'private' or "идел" in message.text.lower() or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id)):
        asyncio.create_task(process_text(message))

# --- ЗАПУСК ---
async def main():
    app = web.Application(); app.router.add_get("/", lambda r: web.Response(text="Idel Overlord Online"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
