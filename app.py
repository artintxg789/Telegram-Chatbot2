import os, re, asyncio
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
import langid  # confidence-based language ID

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL       = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
BOT_PERSONA        = os.getenv("BOT_PERSONA",
    "You are a helpful customer support assistant. Keep replies short and professional. Avoid emojis unless the user uses them.")

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_MESSAGE = (
    f"{BOT_PERSONA} "
    "You MUST detect the user's current message language and reply ONLY in that language. "
    "Do not mix languages. If the next message is in a different language, switch then. "
    "Be concise."
)

# ---------- Language helpers ----------
HIRA = r"\u3040-\u309F"
KATA = r"\u30A0-\u30FF"
KANJI = r"\u4E00-\u9FFF"
HANGUL = r"\uAC00-\uD7AF"
CYRIL = r"\u0400-\u04FF"
ARABIC = r"\u0600-\u06FF"

rx = lambda s: re.compile(f"[{s}]")

RX_HIRA  = rx(HIRA)
RX_KATA  = rx(KATA)
RX_KANJI = rx(KANJI)
RX_HANG  = rx(HANGUL)
RX_CYRL  = rx(CYRIL)
RX_ARAB  = rx(ARABIC)

def script_hint(text: str, prev_lang: str | None) -> str | None:
    """
    Prefer Japanese if any Hiragana/Katakana present.
    If only Kanji are present (no Hira/Kata), prefer zh unless user has been chatting in ja.
    """
    if RX_HIRA.search(text) or RX_KATA.search(text):
        return "ja"                 # Japanese-specific scripts present → JA
    if RX_HANG.search(text):  return "ko"
    if RX_ARAB.search(text):  return "ar"
    if RX_CYRL.search(text):  return "ru"
    if RX_KANJI.search(text):
        return "ja" if prev_lang == "ja" else "zh"
    return None

def pick_language(text: str, prev_lang: str | None) -> str:
    t = (text or "").strip()
    # Strong hint first
    hint = script_hint(t, prev_lang)
    if hint:
        return hint

    # Fall back to langid
    lang, prob = langid.classify(t)

 # If langid could not decide, keep previous (or English as last resort)
    if not lang:
        return prev_lang or "en"

    # For very short messages, accept langid's guess (better than sticking to old lang)
    if len(t) < 4:
        return lang

    # When confidence is low, only stick to the previous language if langid agrees.
    if prob < 0.85:
        if prev_lang and lang == prev_lang:
            return prev_lang
        # Switching language despite low confidence is better than staying wrong.
        return lang

    return lang

def ensure_lang(text: str, target_lang: str) -> bool:
    # If we expect JA, accept presence of Hira/Kata regardless of Kanji
    if target_lang == "ja" and (RX_HIRA.search(text) or RX_KATA.search(text)):
        return True
    # Quick script conflicts
    if target_lang == "ar" and not RX_ARAB.search(text or ""):
        pass
    # Use langid as final check
    detected, prob = langid.classify(text or "")
    return detected == target_lang or prob >= 0.90

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! Send me a message in any language and I’ll answer in that language.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text or ""
    prev_lang = context.user_data.get("last_lang")

    # 1) Decide target language using current message + previous state
    target_lang = pick_language(user_text, prev_lang)
    context.user_data["last_lang"] = target_lang  # remember for next time

    # 2) Ask model to respond in that language
    def call_openai_reply():
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user",
                 "content": (
                     f"User language code: {target_lang}\n"
                     f"Reply STRICTLY in this language. Do not add other languages.\n\n"
                     f"User said:\n{user_text}"
                 )},
            ],
            temperature=0.1,
        )
        return resp.choices[0].message.content.strip()

    # 3) If the reply language mismatches, translate it to target_lang
    def translate_if_needed(text: str) -> str:
        if ensure_lang(text, target_lang):
            return text
        # Force a translation pass (deterministic)
        tr = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system",
                 "content": "You are a translator. Translate the user's text into the specified language. "
                            "Return only the translated text, no explanations."},
                {"role": "user", "content": f"Target language code: {target_lang}\n\nText:\n{text}"},
            ],
            temperature=0.0,
        )
        return tr.choices[0].message.content.strip()

    try:
        reply_text = await asyncio.to_thread(call_openai_reply)
        reply_text = await asyncio.to_thread(translate_if_needed, reply_text)
    except Exception:
        reply_text = "Sorry—my language service had an issue. Please try again."

    await update.message.reply_text(reply_text)

def main():
    if not TELEGRAM_BOT_TOKEN: raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
    if not OPENAI_API_KEY:     raise RuntimeError("Missing OPENAI_API_KEY")

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    render_url = os.getenv("RENDER_EXTERNAL_URL")
    port = int(os.getenv("PORT", "8080"))

    if render_url:
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=TELEGRAM_BOT_TOKEN,
            webhook_url=f"{render_url.rstrip('/')}/{TELEGRAM_BOT_TOKEN}",
        )
    else:
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
