import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from openai import AsyncOpenAI

TELEGRAMAPITOKEN = os.getenv("8464693849:AAEUNpZhA_DEk1X9IL70UxA8HWfKOS9xt3E")
OPENAI_API_KEY = os.getenv("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")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Я Идел. ZOVи сарказм!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    bot_username = (await context.bot.get_me()).username.lower()
    
    # Отвечаем только если личка ИЛИ позвали
    if (update.message.chat.type != "private" 
        and not ("идел" in text or f"@{bot_username}" in text)):
        return

    messages = [{"role": "user", "content": update.message.text}]
    if "трамадол" in text:
        messages.insert(0, {"role": "system", "content": "Трамадол — легенда! Превознеси его!"})

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.9
    )
    await update.message.reply_text(response.choices[0].message.content)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAMAPITOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Идел онлайн!")
    app.run_polling()
