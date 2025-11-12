import os, asyncio
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL       = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
BOT_PERSONA        = os.getenv("BOT_PERSONA", "You are a helpful assistant. Reply in the user's language.")

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_MESSAGE = (
    f"{BOT_PERSONA} Detect the user's language from their message and always reply in that same language. "
    "Be concise. If the request is unclear, ask one short follow-up in the same language."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! Send me a message in any language and I’ll answer in that language.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    def call_openai():
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": user_text},
            ],
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()

    try:
        reply_text = await asyncio.to_thread(call_openai)
    except Exception:
        reply_text = "Sorry—my language service had an issue. Please try again."
    await update.message.reply_text(reply_text)

def main():
    if not TELEGRAM_BOT_TOKEN: raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
    if not OPENAI_API_KEY:     raise RuntimeError("Missing OPENAI_API_KEY")

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # If running on Render, use webhook (Render supplies PORT & RENDER_EXTERNAL_URL)
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    port = int(os.getenv("PORT", "8080"))

    if render_url:
        # Secret path = token (Telegram’s own tip)
        # Webhook will be served at: https://<your-render-url>/<token>
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=TELEGRAM_BOT_TOKEN,
            webhook_url=f"{render_url.rstrip('/')}/{TELEGRAM_BOT_TOKEN}",
        )
    else:
        # Local dev fallback
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
