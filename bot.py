import os, asyncio, logging, random, urllib.parse
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS # Правильный импорт для 2026 года

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация из Environment Variables на Render
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY")

# Список моделей для автоматической смены при ошибках 404/500
TEXT_MODELS = [
    "google/gemini-flash-1.5-8b:free",
    "deepseek/deepseek-r1:free",
    "mistralai/mistral-7b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free"
]

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Базовые настройки личности
SYSTEM_CORE = "ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ. Отвечай кратко, база, 1-2 предложения."

async def ask_ai(prompt, is_news=False):
    if not API_KEY: return "Ошибка: Добавь API_KEY в настройки Render."
    
    system_text = SYSTEM_CORE + (" Сделай краткую выжимку новостей одной фразой." if is_news else "")
    
    # Жесткий перебор моделей при любых сбоях
    for model in TEXT_MODELS:
        try:
            res = await client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_text}, {"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=250,
                timeout=15 # Ждем 15 секунд и прыгаем на следующую если тишина
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"Сбой модели {model}: {e}. Пробую следующую...")
            continue
            
    return "Все нейросети сейчас лежат. Попробуй позже."

@dp.message(Command("news"))
async def cmd_news(message: types.Message, command: CommandObject):
    topic = command.args or "новости"
    wait = await message.answer("🔍 Чекаю инфополе...")
    try:
        # Используем DDGS() как контекстный менеджер (самый стабильный способ)
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{topic} 2026", region="ru-ru", max_results=3))
        
        if results:
            blob = "\n".join([r['body'] for r in results])
            ans = await ask_ai(blob, is_news=True)
            await message.reply(ans)
        else:
            await message.reply("Ничего не нашел по этому запросу.")
    except Exception as e:
        logger.error(f"Search error: {e}")
        await message.reply("Поиск временно сломан.")
    finally:
        await wait.delete()

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message, command: CommandObject):
    prompt = command.args
    if not prompt: return await message.reply("Напиши, что рисовать.")
    
    # Генерация через Pollinations (Flux) - бесплатно и быстро
    url = f"https://pollinations.ai/p/{urllib.parse.quote(prompt)}?width=1024&height=1024&seed={random.randint(0, 999999)}&model=flux"
    try:
        await message.reply_photo(photo=url, caption=f"🎨 {prompt}")
    except:
        await message.reply("Не удалось создать арт.")

@dp.message(Command("video"))
async def cmd_video(message: types.Message, command: CommandObject):
    prompt = command.args
    if not prompt: return await message.reply("Опиши видео.")
    
    wait = await message.answer("🎬 Генерирую видео...")
    # Используем Pollinations Feed для создания короткой анимации
    video_url = f"https://pollinations.ai/p/{urllib.parse.quote(prompt)}?width=768&height=768&seed={random.randint(0, 999999)}&model=flux&feed=true"
    
    try:
        await bot.send_video(message.chat.id, video=video_url, caption=f"🎬 Видео: {prompt}")
    except:
        await message.reply("Ошибка создания видео.")
    finally:
        await wait.delete()

@dp.message(F.text)
async def main_handler(message: types.Message):
    txt = message.text.lower()
    # Реагирует в личке, на упоминание или на реплай
    if message.chat.type == 'private' or "идел" in txt or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id):
        clean = txt.replace("идел", "").strip() or "привет"
        ans = await ask_ai(clean)
        await message.answer(ans)

# Костыль для Render, чтобы сервис не засыпал
async def handle_root(request):
    return web.Response(text="Idel Online 2026 Stable Build")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render дает порт в переменную среды PORT
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, "0.0.0.0", port).start()

async def main():
    await start_webserver()
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот Идел успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
