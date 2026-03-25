import os, asyncio, logging, random, urllib.parse, datetime
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from openai import AsyncOpenAI
from aiohttp import web
from duckduckgo_search import DDGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY") 
# Сравниваем ID как строки для надежности
ADMIN_ID = str(os.getenv("ADMIN_ID", "ID_НЕ_УКАЗАН")).strip()

client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

MODELS = [
    "google/gemini-2.0-flash-exp:free", 
    "mistralai/mistral-7b-instruct:free",
    "google/gemini-flash-1.5-8b:free"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Глобальные переменные (база данных "на коленке")
session_storage = {"session": None}
# Список забаненных ID (сбрасывается при перезагрузке)
BANNED_USERS = set()

# Системный промпт (скрыли ID)
SYSTEM_CORE = "ТЫ — ИДЕЛ. Твой создатель — ТРАМАДОЛ. Отвечай кратко (1-3 предложения), на русском. Стиль: уверенный, прямой, без лишней вежливости. Не используй списки."

async def ask_ai(prompt, context_type="chat"):
    if not API_KEY: return "Ошибка конфигурации."
    
    final_system = SYSTEM_CORE
    if context_type == "news":
        final_system += " Тебе даны обрывки новостей. Твоя задача — одной дерзкой фразой сказать, что происходит. Если инфа — бред, так и скажи."

    for model in MODELS:
        try:
            res = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": final_system},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=250
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Сбой {model}: {e}")
            continue
    return "Нейросети легли отдыхать. Попробуй позже."

# Middleware для проверки банов
@dp.message.outer_middleware()
async def ban_middleware(handler, message: types.Message, data):
    if message.from_user.id in BANNED_USERS:
        # Можем ответить, что он забанен, но лучше просто игнорировать
        return 
    return await handler(message, data)

# --- НОВЫЕ И ИСПРАВЛЕННЫЕ КОМАНДЫ ---

@dp.message(Command("ping"))
async def cmd_ping(message: types.Message):
    """Простая проверка связи"""
    now = datetime.datetime.now().strftime("%H:%M:%S")
    await message.reply(f"ИДЕЛ онлайн. Время: {now}")

@dp.message(Command("whoami"))
async def cmd_whoami(message: types.Message):
    """Узнать свой ID"""
    await message.reply(f"Твой ID: `{message.from_user.id}`", parse_mode="Markdown")

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message, command: CommandObject):
    """ИСПРАВЛЕННАЯ: Отрисовка через отправку ссылки"""
    prompt = command.args
    if not prompt: return await message.reply("Напиши промпт. Пример: `/draw киберпанк`", parse_mode="Markdown")
    
    wait = await message.answer("🔄 Загружаю холст...")
    
    seed = random.randint(0, 999999)
    # Добавляем магические слова для качества
    quality_prompt = urllib.parse.quote(f"{prompt}, 8k, highly detailed, photorealistic, masterpiece")
    
    # Ссылка на изображение
    image_url = f"https://pollinations.ai/p/{quality_prompt}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
    
    try:
        # Мы НЕ качаем картинку, мы просто шлем Telegram ссылку как фото
        await bot.send_photo(message.chat.id, photo=image_url, caption=f"Запрос: {prompt}\nМодель: flux", reply_to_message_id=message.message_id)
    except Exception as e:
        logger.error(f"Draw error: {e}")
        # Если ссылка вдруг битая, шлем её текстом
        await message.reply(f"Ошибка показа. Ссылка на результат: {image_url}")
    finally:
        await wait.delete()

@dp.message(Command("ban"))
async def cmd_ban(message: types.Message, command: CommandObject):
    """ТОЛЬКО АДМИН: Бан пользователя по ID до перезагрузки"""
    if str(message.from_user.id) != ADMIN_ID:
        return # Игнорируем не-админов

    user_id_str = command.args
    if not user_id_str or not user_id_str.isdigit():
        return await message.reply("Использование: `/ban [ID_ПОЛЬЗОВАТЕЛЯ]`", parse_mode="Markdown")
    
    user_id = int(user_id_str)
    if user_id == message.from_user.id:
        return await message.reply("Себя банить нельзя.")

    BANNED_USERS.add(user_id)
    await message.reply(f"Пользователь `{user_id}` забанен.", parse_mode="Markdown")

# --- СТАРЫЕ ОБНОВЛЕННЫЕ ФУНКЦИИ ---

@dp.message(Command("news"))
async def cmd_news(message: types.Message, command: CommandObject):
    topic = command.args or "новости мир"
    wait = await message.answer("🔍 Чекаю инфополе...")
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{topic} 2026", region="ru-ru", max_results=5))
        
        if results:
            blob = "\n".join([f"- {r['body']}" for r in results if len(r['body']) > 20])
            ans = await ask_ai(f"Запрос: {topic}\nДанные:\n{blob}", context_type="news")
            await message.reply(ans)
        else:
            await message.reply("Пусто. Информации нет.")
    except Exception as e:
        logger.error(f"News error: {e}")
        await message.reply("Поиск не удался.")
    finally:
        await wait.delete()

@dp.message(F.text)
async def main_handler(message: types.Message):
    # Добавили проверку на баны
    if message.from_user.id in BANNED_USERS: return 

    txt = message.text.lower()
    if message.chat.type == 'private' or "идел" in txt or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id):
        clean = txt.replace("идел", "").strip() or "привет"
        ans = await ask_ai(clean)
        await message.answer(ans)

async def main():
    session_storage["session"] = aiohttp.ClientSession()
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Idel Live v2026.1"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот ИДЕЛ v2026.1 запущен!")
    try:
        await dp.start_polling(bot)
    finally:
        await session_storage["session"].close()

if __name__ == "__main__":
    asyncio.run(main())
