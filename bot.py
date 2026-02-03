import os
print("🚀 Запуск Идела...")

# Render env отладка
token = os.getenv("8464693849:AAEUNpZhA_DEk1X9IL70UxA8HWfKOS9xt3E")
print(f"TOKEN: {'OK' if token else '❌ НЕ НАЙДЕН'}")
print(f"OPENAI: {'OK' if os.getenv('OPENAI_API_KEY') else '❌ НЕ НАЙДЕН'}")

if not token:
    print("❌ УСТАНОВИ TELEGRAMAPITOKEN в Environment!")
    exit(1)

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update
from openai import AsyncOpenAI
import asyncio

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Идел жив!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "идел" not in text:
        return
        
    await update.message.reply_text("Идел тут! Пока без ИИ.")

print("✅ Идел готов!")
app = ApplicationBuilder().token(token).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
