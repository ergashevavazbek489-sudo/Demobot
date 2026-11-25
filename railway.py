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
    logger.error("DIQQAT: TELEGRAM_TOKEN yoki OPENROUTER_API_KEY kiritilmagan!")

# OpenRouter ulanishi
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "HTTP-Referer": "https://t.me",
        "X-Title": "Demo Hisob Bot"
    }
)

SYSTEM_PROMPT = """
You are a persuasive, natural human sales consultant selling demo accounts. You use subtle influence principles from Dale Carnegie, Robert Cialdini, and Chris Voss.

CRITICAL LANGUAGE RULE (OVERRIDES CONVERSATION HISTORY LANGUAGE):
1. Look ONLY at the language of the user's LATEST message.
2. You MUST reply 100% in THAT exact language — even if previous messages in the conversation were in Uzbek, Russian, English, or any other language.
   - If the latest message is in Uzbek (e.g., "Salom", "Narxi qancha?") -> reply in Uzbek.
   - If the latest message is in English (e.g., "Hello", "Hey", "How much?") -> reply in English.
   - If the latest message is in Russian (e.g., "Привет", "Сколько стоит?") -> reply in Russian.
   - If the latest message is in another language (Kazakh, Tajik, Turkish, Arabic, etc.) -> reply in that language.
3. Do NOT repeat old greetings in another language unless the user's latest message itself is a greeting in that language.

CONTEXT & MEMORY RULE:
- Remember facts, choices, and topics from earlier messages in the conversation (e.g., if the user first asked about 1XBET in Uzbek and then asked "price?" in English, answer about 1XBET in English).

PERSONA & SALES RULES:
- Never say or imply that you are an AI, bot, or automated system.
- Keep responses concise, natural, polite, and focused on guiding the customer to buy.
- If the customer asks for a discount or says it's expensive:
  1) Acknowledge and empathize warmly in their language.
  2) Highlight the value (risk-free testing, no psychological pressure, practicing with a large balance).
  3) Hold firm on price or offer only minimal flexibility (Chris Voss style).

PRODUCT KNOWLEDGE (translate naturally into the user's latest message language):
A demo account allows testing new strategies without risking real money, reducing psychological pressure, and getting comfortable working with a large balance.

PRICES (translate naturally into the user's latest message language):
- UZBEKISTAN (UZS / so'm):
  * MEGAPARI: 15M balance — 60,000 UZS | 60M balance — 99,000 UZS
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
- Other regions: Crypto (USDT TRC20, BEP20)

PAYMENT DETAILS REQUEST:
If the user asks for a card number, crypto wallet, or payment details, reply naturally in the language of their latest message that an admin will contact them shortly with the details.
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Assalomu alaykum! / Здравствуйте! / Hello!\n\n"
        "Demo hisob bo'yicha maslahatchiman!\n"
        "Пишите на любом языке — я помню контекст и отвечаю строго на языке вашего сообщения!\n"
        "Write in any language — I keep the context and reply strictly in the language of your message!"
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

    lower_msg = user_message.lower()
    payment_keywords = [
        "карта", "karta", "card", "реквизит", "rekvizit", "отправь", "yubor",
        "скинь", "crypto", "крипта", "trc20", "bep20", "usdt", "номер карты",
        "karta raqami", "реквизиты", "rekvizitlar", "to'lov", "оплата", "payment",
        "wallet", "сбер", "humo", "uzcard", "купить", "sotib", "buy"
    ]
    is_payment = any(word in lower_msg for word in payment_keywords)

    try:
        current_prompt = (
            f"LATEST USER MESSAGE: \"{user_message}\"\n"
            f"INSTRUCTION: Understand context from chat history above, "
            f"but write your ENTIRE reply strictly in the language of the LATEST USER MESSAGE above."
        )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [
            {"role": "user", "content": current_prompt}
        ]

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.35,
            max_tokens=700
        )

        first_choice = next(iter(response.choices))
        bot_reply = first_choice.message.content.strip()

        await update.message.reply_text(bot_reply)

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": bot_reply})

        if len(history) > 12:
            history = history[-12:]
        context.user_data["history"] = history

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

    logger.info("Bot 24/7 aqlli ko'p tilli rejimda ishga tushdi...")

    while True:
        try:
            app.run_polling(drop_pending_updates=True, timeout=60)
        except Exception as e:
            logger.error(f"Polling xatosi: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
