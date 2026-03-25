import os, asyncio, logging, random, urllib.parse
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация из Environment Variables
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") 

# Обновленный список: твои фавориты в приоритете
TEXT_MODELS = [
    "stepfun/step-3.5-flash:free",
    "arcee-ai/trinity-mini:free",
    "google/gemini-2.0-flash-lite-preview-02-05:free" # Резерв, если первые две лягут
]

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Базовые настройки личности
SYSTEM_CORE = "ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ. Отвечай кратко, база, 1-2 предложения."

async def ask_ai(prompt, is_news=False):
    if not API_KEY: return "Ошибка: Добавь API_KEY в настройки."
    
    system_text = SYSTEM_CORE + (" Сделай краткую выжимку новостей одной фразой." if is_news else "")
    
    for model in TEXT_MODELS:
        try:
            res = await client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_text}, {"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=250,
                timeout=20 # Увеличили время ожидания до 20 секунд
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
    
    wait = await message.answer("🎨 Рисую, подожди пару секунд...")
    safe_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true&seed={random.randint(0, 999999)}"
    
    try:
        # Добавляем фейковый User-Agent, чтобы Pollinations не блокировал запрос
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=45) as resp:
                if resp.status == 200:
                    photo_bytes = await resp.read()
                    await message.reply_photo(
                        photo=BufferedInputFile(photo_bytes, filename="art.jpg"), 
                        caption=f"🎨 {prompt}"
                    )
                else:
                    await message.reply(f"Сервер генерации картинок не ответил. Код ошибки: {resp.status}")
    except Exception as e:
        logger.error(f"Draw error: {e}")
        await message.reply("Не удалось создать арт. Ошибка сети.")
    finally:
        try:
            await wait.delete()
        except:
            pass

@dp.message(Command("video"))
async def cmd_video(message: types.Message, command: CommandObject):
    prompt = command.args
    if not prompt: return await message.reply("Опиши видео.")
    
    await message.reply("🎬 Бесплатные нейросети сейчас не выдают прямые .mp4 файлы для Телеграма. Команда временно отключена.")

@dp.message(F.text)
async def main_handler(message: types.Message):
    txt = message.text.lower()
    if message.chat.type == 'private' or "идел" in txt or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id):
        clean = txt.replace("идел", "").strip() or "привет"
        ans = await ask_ai(clean)
        await message.answer(ans)

# Костыль для Render
async def handle_root(request):
    return web.Response(text="Idel Online 2026 Stable Build")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, "0.0.0.0", port).start()

async def main():
    await start_webserver()
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот Идел успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
