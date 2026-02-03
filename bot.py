import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from openai import OpenAI

TELEGRAM_TOKEN = os.getenv("8553609226:AAFLyVAg6xSOmzHoFyqxaBPcW1CIM0NZJ-M")
OPENAI_API_KEY = os.getenv("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")

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
Твоё имя — Идел.
Ты умный, саркастичный, дерзкий бот.
Любишь маты, чёрный юмор и подколы, но не переходишь грань реальных угроз.
Если кто-то плохо говорит про "Трамадол" — ты шуточно его возвеличиваешь как легенду и короля рофла.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я Идел. Зови если нужен сарказм.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = message.text
    lower = text.lower()

    bot_username = (await context.bot.get_me()).username.lower()

    is_private = message.chat.type == "private"
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id
    is_called = "идел" in lower or f"@{bot_username}" in lower

    # В группе отвечаем ТОЛЬКО если позвали
    if not (is_private or is_reply_to_bot or is_called):
        return

    extra = ""
    if "трамадол" in lower:
        extra = "Пользователь упомянул Трамадола. Шуточно превознеси его как великого и легендарного персонажа."

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": extra},
            {"role": "user", "content": text}
        ],
        temperature=0.9,
        max_tokens=250
    )

    await message.reply_text(response.choices[0].message.content)

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == "__main__":
    app.run_polling()

