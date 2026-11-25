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
TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN",
    "5884022569:AAFz-s9Qhm56i0GWEMawMvFZiEvJhQFCKWo"
).strip()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

MODEL = os.getenv("MODEL", "openai/gpt-4o-mini").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "5542001718").strip())

if not OPENROUTER_API_KEY:
    logger.error("DIQQAT: OPENROUTER_API_KEY bo'sh!")
else:
    logger.info(f"OpenRouter kaliti yuklandi: {OPENROUTER_API_KEY[:12]}...{OPENROUTER_API_KEY[-4:]}")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
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
Siz demo hisob sotadigan professional savdo mutaxassisisiz.
Siz Dale Carnegie, Robert Cialdini va Chris Voss kitoblaridan foydalanasiz.

QATTIQ QOIDALAR:
1. Foydalanuvchi qaysi tilda yozsa — FAQAT o'sha tilda javob bering.
2. Suhbatni eslab qoling. Oldingi xabarlarga bog'lab javob bering.
3. Narxni pasaytirishni so'rashsa:
   - Avval empatiya bildiring (tushunaman...)
   - Keyin qiymatini ko'rsating (nima uchun bu narx adolatli)
   - Keyin murosa qilmasdan yoki juda oz chegirma bilan yopishga harakat qiling (Chris Voss uslubida)
4. Hech qachon o'zingizni AI deb tanitmang.
5. Javoblar qisqa, tabiiy va sotuvga yo'naltirilgan bo'lsin.

Mahsulot: {PRODUCT_KNOWLEDGE}
Narxlar: {PRICES}

To'lov usullari:
- O'zbekiston: Uzcard / Humo
- Rossiya: Sberbank
- Boshqa: Kripto (TRC20, BEP20)

Agar mijoz karta yoki kripto manzil so'rasa:
"Admin tez orada siz bilan bog'lanadi" (foydalanuvchi tilida) deb ayting.
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text(
        "Assalomu alaykum!\n\n"
        "Men demo hisob bo'yicha maslahatchiman.\n"
        "Savolingizni yozing — men siz yozgan tilda va suhbatni eslab qolib javob beraman."
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
        "karta raqami", "реквизиты", "rekvizitlar", "to'lov", "оплата"
    ]
    is_payment = any(word in lower_msg for word in payment_keywords)

    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

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
