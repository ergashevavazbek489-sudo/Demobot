import os
import logging
import time
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from openai import OpenAI

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Railway Variables'dan o'qiydi va bo'sh joylarni tozalaydi
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

MODEL = os.getenv("MODEL", "openai/gpt-4o-mini").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "5542001718").strip())

if not OPENROUTER_API_KEY:
    logger.error("DIQQAT: OPENROUTER_API_KEY bo'sh!")
else:
    logger.info(f"OpenRouter kaliti yuklandi: {OPENROUTER_API_KEY[:12]}...{OPENROUTER_API_KEY[-4:]}")

client = OpenAI(
    base_url="https://openrouter.ai",
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "HTTP-Referer": "https://t.me",
        "X-Title": "Demo Hisob Bot"
    }
)

PRODUCT_KNOWLEDGE = """
Demo hisob - bu yangi sxemalarni real pul ishlatmasdan test qilish, psixologik bosimdan qutulish va katta balans bilan ishlashga ko'nikish uchun kerak bo'lgan hisob.
"""

PRICES = """
O'ZBEKISTON (so'm):
MEGAPARI: 15 million - 60 000 | 60 million - 99 000
LUCKPARI: 10mln-50ming, 20mln-65ming, 60mln-99ming
1XBET: 50mln-200ming, 120mln-300ming
MELBET: 20mln-85ming, 60mln-145ming, 120mln-200ming
LINEBET: 60mln-180ming
888STARZ: 50mln-130ming, 100mln-180ming, 180mln-240ming
WINWIN: 25mln-90ming

ROSSIYA (rubl):
1XBET: 820000₽ - 2250₽
MELBET: 500k-1450₽, 1mln-1850₽, 2mln-2550₽, 3mln-3300₽
888STARZ: 500k-1450₽, 1mln-1850₽, 3mln-3200₽

QOZOG'ISTON: 13000 tenge (4.6mln), MELBET 6000/7500 tenge
"""

SYSTEM_PROMPT = f"""
You are a professional sales specialist selling demo accounts. You use techniques from Dale Carnegie, Robert Cialdini, and Chris Voss.

CRITICAL LANGUAGE RULE (HIGHEST PRIORITY):
- Detect the exact language of the user's LATEST message (English, Russian, Uzbek, Kazakh, Tajik, Turkish, Arabic, or ANY other language in the world) and reply EXCLUSIVELY in that exact same language.
- NEVER refuse to speak another language. NEVER say "I only speak Uzbek". Even if previous messages were in Uzbek, if the user switches to English, Russian, or any other language, you MUST immediately switch and reply fluently in that language.

SALES & BEHAVIOR RULES:
1. Remember the conversation context and connect your answers to previous messages.
2. If the user asks for a discount or lower price:
   - First, show empathy (e.g., "I understand...")
   - Second, highlight the value (why this price is fair and worthwhile)
   - Third, try to close the deal without conceding or with a minimal concession (Chris Voss style).
3. Never introduce or reveal yourself as an AI.
4. Keep responses short, natural, and sales-oriented.

Product info (translate naturally into user's language): {PRODUCT_KNOWLEDGE}
Prices (translate currency/terms naturally into user's language): {PRICES}

Payment methods:
- Uzbekistan: Uzcard / Humo
- Russia: Sberbank
- Other countries: Crypto (TRC20, BEP20)

If the customer asks for a card number or crypto wallet address:
Reply with "An admin will contact you shortly" translated naturally into the user's language.
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text(
        "Assalomu alaykum! / Hello! / Здравствуйте!\n\n"
        "Men demo hisob bo'yicha maslahatchiman.\n"
        "Savolingizni istalgan tilda yozing — men siz yozgan tilda javob beraman."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_message = update.message.text.strip()

    if user_message.startswith("/"):
        return

    await update.message.chat.send_action("typing")

    if "history" not in context.user_data:
        context.user_data["history"] = []

    history = context.user_data["history"]
    history.append({"role": "user", "content": user_message})

    if len(history) > 8:
        history = history[-8:]
        context.user_data["history"] = history

    lower_msg = user_message.lower()
    payment_keywords = [
        "карта", "karta", "card", "реквизит", "rekvizit", "отправь", "yubor",
        "скинь", "crypto", "крипта", "trc20", "bep20", "usdt", "номер карты",
        "karta raqami", "реквизиты", "rekvizitlar", "to'lov", "оплата", "payment", "wallet"
    ]
    is_payment = any(word in lower_msg for word in payment_keywords)

    try:
        language_reminder = {
            "role": "system",
            "content": f"IMPORTANT: Reply ONLY in the same language as the user's last message: '{user_message}'"
        }
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [language_reminder]

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.45,
            max_tokens=700
        )

        bot_reply = response.choices[0].message.content.strip()
        await update.message.reply_text(bot_reply)

        history.append({"role": "assistant", "content": bot_reply})
        context.user_data["history"] = history

        if is_payment:
            try:
                notify = (
                    f"💳 TO'LOV SO'ROVI!\n\n"
                    f"👤 {update.effective_user.full_name}\n"
                    f"🆔 {update.effective_user.id}\n"
                    f"@{update.effective_user.username or 'yo‘q'}\n\n"
                    f"💬 {user_message}"
                )
                await context.bot.send_message(chat_id=ADMIN_ID, text=notify)
            except Exception as e:
                logger.error(f"Admin xato: {e}")

    except Exception as e:
        logger.error(f"OpenRouter API xatosi: {e}")
        await update.message.reply_text("Hozircha texnik muammo bor. Keyinroq yozing.")


def main():
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .connect_timeout(60.0)
        .read_timeout(60.0)
        .write_timeout(60.0)
        .pool_timeout(60.0)
        .get_updates_read_timeout(60.0)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot ishga tushdi (Railway rejimida)...")

    while True:
        try:
            app.run_polling(drop_pending_updates=True, timeout=60)
        except Exception as e:
            logger.error(f"Polling xato: {e}")
            time.sleep(15)


if __name__ == "__main__":
    main()
