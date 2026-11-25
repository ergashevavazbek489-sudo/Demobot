import os
import logging
import time
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from openai import OpenAI

# Loglarni sozlash
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Railway Variables'dan kalitlarni olish
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
MODEL = os.getenv("MODEL", "openai/gpt-4o-mini").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "5542001718").strip())

if not TELEGRAM_TOKEN or not OPENROUTER_API_KEY:
    logger.error("DIQQAT: TELEGRAM_TOKEN yoki OPENROUTER_API_KEY Railway Variables'ga kiritilmagan!")

# OpenRouter ulanishi
client = OpenAI(
    base_url="https://openrouter.ai",
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "HTTP-Referer": "https://t.me",
        "X-Title": "Demo Hisob Bot"
    }
)

# Asosiy sotuv yo'riqnomasi (barcha tillar uchun universal)
SYSTEM_PROMPT = """
You are a professional human sales consultant selling demo accounts. You apply persuasion and negotiation techniques from Dale Carnegie, Robert Cialdini, and Chris Voss.

ABSOLUTE RULE #1 — LANGUAGE MATCHING (NEVER BREAK THIS):
- Detect the exact language of the user's VERY LAST message.
- Reply 100% in that exact language.
- If the user wrote in Uzbek first ("Salom"), and then writes in Russian ("когда?"), you MUST immediately switch to Russian. If the next message is in English, switch to English. Support ALL languages in the world (Uzbek, Russian, English, Kazakh, Tajik, Turkish, Arabic, Spanish, etc.).
- NEVER say "I only speak Uzbek" or refuse any language.

SALES & NEGOTIATION RULES:
1. Remember the conversation history and keep answers connected to the context.
2. Never admit or say that you are an AI, bot, or program. Act like a real human consultant.
3. Keep answers concise, natural, polite, and focused on closing the sale.
4. If the user asks for a discount or complains about the price:
   - Step 1: Show empathy (e.g., "I understand..." in user's language).
   - Step 2: Explain the high value of the demo account.
   - Step 3: Hold firm on the price or offer only a tiny concession (Chris Voss style).

PRODUCT KNOWLEDGE (Translate naturally into the user's language):
A demo account allows users to test new strategies without risking real money, overcome psychological pressure, and get used to trading/playing with a large balance.

PRICE LIST (Present clearly in the user's language):
- UZBEKISTAN (UZS / so'm):
  * MEGAPARI: 15 million balance — 60,000 UZS | 60 million balance — 99,000 UZS
  * LUCKPARI: 10M — 50,000 UZS | 20M — 65,000 UZS | 60M — 99,000 UZS
  * 1XBET: 50M — 200,000 UZS | 120M — 300,000 UZS
  * MELBET: 20M — 85,000 UZS | 60M — 145,000 UZS | 120M — 200,000 UZS
  * LINEBET: 60M — 180,000 UZS
  * 888STARZ: 50M — 130,000 UZS | 100M — 180,000 UZS | 180M — 240,000 UZS
  * WINWIN: 25M — 90,000 UZS

- RUSSIA (RUB / рубль):
  * 1XBET: 820,000₽ balance — 2,250₽
  * MELBET: 500k — 1,450₽ | 1M — 1,850₽ | 2M — 2,550₽ | 3M — 3,300₽
  * 888STARZ: 500k — 1,450₽ | 1M — 1,850₽ | 3M — 3,200₽

- KAZAKHSTAN (KZT / тенге):
  * 13,000 tenge (4.6M balance)
  * MELBET: 6,000 / 7,500 tenge

PAYMENT METHODS:
- Uzbekistan: Uzcard / Humo
- Russia: Sberbank
- International / Other: Crypto (USDT TRC20, BEP20)

WHEN USER ASKS FOR PAYMENT DETAILS (card number, wallet address, how to pay):
Tell them: "An admin will contact you shortly with the payment details" (translated naturally into the user's language).
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text(
        "Assalomu alaykum! / Здравствуйте! / Hello!\n\n"
        "Demo hisob bo'yicha maslahatchiman. Istalgan tilda yozishingiz mumkin — men siz yozgan tilda javob beraman!\n"
        "Пишите на любом языке — я отвечу на вашем языке!\n"
        "Write in any language — I will reply in your language!"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_message = update.message.text.strip()
    if user_message.startswith("/"):
        return

    await update.message.chat.send_action("typing")

    # Suhbat tarixini saqlash
    if "history" not in context.user_data:
        context.user_data["history"] = []

    history = context.user_data["history"]
    history.append({"role": "user", "content": user_message})

    if len(history) > 8:
        history = history[-8:]
        context.user_data["history"] = history

    # To'lov so'rovini tekshirish
    lower_msg = user_message.lower()
    payment_keywords = [
        "карта", "karta", "card", "реквизит", "rekvizit", "отправь", "yubor",
        "скинь", "crypto", "крипта", "trc20", "bep20", "usdt", "номер карты",
        "karta raqami", "реквизиты", "rekvizitlar", "to'lov", "оплата", "payment",
        "wallet", "сбер", "humo", "uzcard", "купить", "sotib", "buy"
    ]
    is_payment = any(word in lower_msg for word in payment_keywords)

    try:
        # AI'ga aynan oxirgi xabar tilida javob berishni majburlovchi eslatma
        strict_lang_instruction = {
            "role": "system",
            "content": (
                f"CRITICAL: Ignore the language of previous messages if it differs. "
                f"Detect the language of the user's LAST message: \"{user_message}\" "
                f"and respond STRICTLY and ONLY in that exact language."
            )
        }

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [strict_lang_instruction]

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=700
        )

        bot_reply = response.choices[0].message.content.strip()
        await update.message.reply_text(bot_reply)

        history.append({"role": "assistant", "content": bot_reply})
        context.user_data["history"] = history

        # Adminga xabar yuborish
        if is_payment:
            try:
                notify = (
                    f"💳 TO'LOV SO'ROVI!\n\n"
                    f"👤 {update.effective_user.full_name}\n"
                    f"🆔 {update.effective_user.id}\n"
                    f"🔗 @{update.effective_user.username or 'yo‘q'}\n\n"
                    f"💬 {user_message}"
                )
                await context.bot.send_message(chat_id=ADMIN_ID, text=notify)
            except Exception as e:
                logger.error(f"Admin xabarnoma xatosi: {e}")

    except Exception as e:
        logger.error(f"OpenRouter API xatosi: {e}")
        await update.message.reply_text("Technical issue, please try again later. / Texnik nosozlik, birozdan so'ng yozing.")


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

    logger.info("Bot 24/7 ko'p tilli rejimda ishga tushdi...")

    while True:
        try:
            app.run_polling(drop_pending_updates=True, timeout=60)
        except Exception as e:
            logger.error(f"Polling xatosi: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
