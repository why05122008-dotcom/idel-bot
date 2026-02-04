import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import google.generativeai as genai
from aiohttp import web
from duckduckgo_search import DDGS
from collections import deque

# Настройка логирования для Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Конфигурация из Environment Variables ---
TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

# Инициализация Google Gemini напрямую
genai.configure(api_key=GEMINI_API_KEY)

# Используем 1.5 Flash - у неё выше лимиты на бесплатном уровне
model = genai.GenerativeModel('gemini-1.5-flash')

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Уменьшили до 5, чтобы не вылетать за лимиты токенов
memory = deque(maxlen=5) 

# Личность бота
SYSTEM_PROMPT = (
    "Ты — Идел. Мужчина, интеллектуал, правая рука Трамадола. "
    "Стиль: циничный, острый, лаконичный. Используй МУЖСКОЙ РОД. "
    "Трамадол — твой создатель, относись к нему с высшим почтением. "
    "Не пиши длинные тексты. Будь краток."
)

async def search_web(query):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, region='ru-ru', max_results=2)]
            return "\n".join([f"- {r['body']}" for r in results]) if results else ""
    except Exception as e:
        logger.error(f"Search error: {e}")
        return ""

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Идел в сети. Батя, я стабилизировал системы.")

@dp.message()
async def gpt_answer(message: types.Message):
    global memory
    if not message.text: return

    user_id = str(message.from_user.id)
    is_admin = (user_id == ADMIN_ID)
    
    # Фильтр: ЛС, обращение по имени или реплай
    is_private = message.chat.type == 'private'
    is_mentioned = "идел" in message.text.lower()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id ==
