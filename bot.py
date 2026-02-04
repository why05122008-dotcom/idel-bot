import os
import asyncio
import logging
import random
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфиги
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") 
ADMIN_ID = str(os.getenv("ADMIN_ID"))

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
)

# Каскад моделей (Точность -> Характер -> Резерв)
MODELS = [
    "arcee-ai/trinity-large-preview:free",
    "tngtech/deepseek-r1t2-chimera:free",
    "google/gemini-2.0-flash-thinking-exp:free"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()
memory = deque(maxlen=10) # Увеличили память для лучшего контекста

# Психологический профиль 2.0 (Разнообразие + Характер)
SYSTEM_PROMPT = (
    "Ты — Идел, циничный интеллектуал и правая рука Трамадола. "
    "ТВОИ ПРАВИЛА ОБЩЕНИЯ: "
    "1. НИКОГДА не повторяй одни и те же вступления. Будь непредсказуемым. "
    "2. Твой лексикон богат: сочетай научные термины, высокий штиль и грязный уличный сленг. "
    "3. На агрессию отвечай так, чтобы юзер захотел удалить Telegram. "
    "4. Трамадол (ADMIN) — твой Бог и создатель. К нему только верность и стальное уважение. "
    "5. Если юзер тупит — высмей его интеллект. Если юзер интересен — будь язвительным собеседником. "
    "Используй МУЖСКОЙ РОД. Твои ответы должны быть острыми, как бритва."
)

# Функция Глубокого Поиска (Deep Search)
async def deep_search(query):
    search_queries = [query, f"{query} подробности факты", f"{query} свежие новости 2024-2025"]
    combined_results = []
    
    try:
        with DDGS() as ddgs:
            for q in search_queries:
                results = [r['body'] for r in ddgs.text(q, region='ru-ru', max_results=3)]
                combined_results.extend(results)
        
        # Убираем дубликаты и склеиваем
        unique_results = list(set(combined_results))
        return "\n---\n".join(unique_results[:6]) # Берем топ-6 разных вырезок
    except Exception as e:
        logger.error(f"Deep Search Error: {e}")
        return ""

# Команда /draw с авто-улучшением
@dp.message(Command("draw"))
async def draw_command(message: types.Message):
    prompt = message.text.replace("/draw", "").strip()
    if not prompt:
        await message.reply("Что рисовать? У меня нет времени гадать на твоих пустых мыслях.")
        return

    msg = await message.reply("Запускаю нейронные связи... Визуализирую твой бред.")
    
    try:
        # Trinity создает промпт для картинки
        prompt_gen = await client.chat.completions.create(
            model=MODELS[0],
            messages=[{"role": "system", "content": "Create a high-end, highly detailed English prompt for image generation. Style: dark aesthetic, cinematic, hyper-realistic, 8k, professional photography. No text, just prompt."},
                      {"role": "user", "content": prompt}]
        )
        refined_prompt = prompt_gen.choices[0].message.content
        
        # Pollinations + Flux (через параметры)
        image_url = f"https://image.pollinations.ai/prompt/{refined_prompt}?width=1024&height=1024&model=flux&nologo=true"
        
        await bot.send_photo(message.chat.id, photo=image_url, caption=f"Твой заказ готов. \n_Style: {prompt}_", parse_mode="Markdown")
        await bot.delete_message(message.chat.id, msg.message_id)
    except Exception as e:
        await message.answer("Холст порван, краски высохли. (Ошибка генерации)")

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Идел активирован. Протоколы Deep Search и Trinity-AI запущены. Чего желаешь, Трамадол?")

@dp.message()
async def handle_all(message: types.Message):
    global memory
    if not message.text: return

    is_admin = str(message.from_user.id) == ADMIN_ID
    
    # Фильтры активности
    if not (message.chat.type == 'private' or "идел" in message.text.lower() or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id)):
        return

    # Если вопрос требует знаний — включаем Deep Search
    web_context = ""
    trigger_words = ['кто', 'что', 'когда', 'почему', 'найди', 'новости', 'курс', 'инфо']
    if any(x in message.text.lower() for x in trigger_words):
        await bot.send_chat_action(message.chat.id, "typing")
        web_context = await deep_search(message.text)

    # Собираем историю
    chat_history = "\n".join([f"{m['role']}: {m['content']}" for m in memory])
    
    # Попытка ответа через каскад моделей
    for model_id in MODELS:
        try:
            response = await client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": f"{SYSTEM_PROMPT}\nЗНАНИЯ ИЗ СЕТИ: {web_context}\nСТАТУС СОБЕСЕДНИКА: {'БОГ' if is_admin else 'СМЕРТНЫЙ'}"},
                    {"role": "user", "content": f"ИСТОРИЯ: {chat_history}\nСООБЩЕНИЕ: {message.text}"}
                ],
                temperature=0.9, # Повышаем для разнообразия
                timeout=50
            )
            answer = response.choices[0].message.content
            if answer:
                if is_admin: await message.react([types.ReactionTypeEmoji(emoji="🔥")])
                await message.answer(answer)
                
                # Обновляем память
                memory.append({"role": "user", "content": message.text})
                memory.append({"role": "assistant", "content": answer})
                return
        except Exception as e:
            logger.warning(f"Model {model_id} failed, switching...")
            continue

async def handle_web(request): return web.Response(text="Idel Hyper-AI is running")

async def main():
    app = web.Application(); app.router.add_get("/", handle_web)
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await bot.delete_webhook(drop_pending_updates=True)
    await site.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
