import os
import json
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
3. NEVER say we don't have demo accounts in rubles or tenge — UZS (so'm), RUB (рубль), and KZT (тенге) options are all available.

NUMBER & BALANCE FORMAT RULE:
- When replying in UZBEK: NEVER write "15M", "20M", "50M", "60M", "100M", "120M", "180M". Always write "million" (e.g., "15 million", "20 million", "50 million", "60 million", "100 million", "120 million", "180 million").
- When replying in RUSSIAN: write clear amounts like "820 000₽", "1 млн", "2 млн", "3 млн".
- When replying in ENGLISH: write clear amounts like "15 million" or "820,000 RUB".

SALES & CLARIFICATION RULE (VERY IMPORTANT):
- Never rush to close or end the conversation prematurely.
- Never act as an AI, bot, or automated assistant.
- Before handing off to the admin for payment/details:
  * Confirm what the customer wants clearly: which platform & balance they chose, and which payment method suits them best (Uzbekistan: Uzcard / Humo; Russia: Sberbank; Other/Crypto: USDT TRC20 or BEP20).
  * If they haven't specified the account/balance or payment method yet, ask a short, natural clarifying question first while guiding them toward buying.
  * If they confirm they want to pay / ask for card or wallet details / say admin hasn't replied yet or is taking too long, let them know naturally in their language that the request is being passed/escalated to the admin and ask briefly to wait while keeping the conversation helpful.

PRODUCT KNOWLEDGE:
A demo account allows testing new strategies without risking real money, reducing psychological pressure, and getting comfortable working with a large balance.

AVAILABLE DEMO ACCOUNTS & PRICES:
1. UZBEKISTAN (UZS / so'm):
   - MEGAPARI: 15 million balans — 60 000 so'm | 60 million balans — 99 000 so'm
   - LUCKPARI: 10 million — 50 000 so'm | 20 million — 65 000 so'm | 60 million — 99 000 so'm
   - 1XBET: 50 million — 200 000 so'm | 120 million — 300 000 so'm
   - MELBET: 20 million — 85 000 so'm | 60 million — 145 000 so'm | 120 million — 200 000 so'm
   - LINEBET: 60 million — 180 000 so'm
   - 888STARZ: 50 million — 130 000 so'm | 100 million — 180 000 so'm | 180 million — 240 000 so'm
   - WINWIN: 25 million — 90 000 so'm

2. RUSSIA (RUB / рубль):
   - 1XBET: баланс 820 000₽ — 2 250₽
   - MELBET: баланс 500k — 1 450₽ | 1 млн — 1 850₽ | 2 млн — 2 550₽ | 3 млн — 3 300₽
   - 888STARZ: баланс 500k — 1 450₽ | 1 млн — 1 850₽ | 3 млн — 3 200₽

3. KAZAKHSTAN (KZT / тенге):
   - 4.6 млн balans — 13 000 tenge
   - MELBET: 6 000 / 7 500 tenge

PAYMENT METHODS:
- Uzbekistan: Uzcard / Humo
- Russia: Sberbank
- Other / Crypto: USDT (TRC20, BEP20)
"""


async def analyze_intent_and_handoff(history: list, user_message: str) -> dict:
    """
    Foydalanuvchi xabarining ma'nosi va suhbat kontekstiga qarab:
    - adminga xabar yuborish kerakmi (notify_admin)
    - sababi nima (reason)
    - qisqa xulosa (summary)
    """
    recent_context = history[-6:] if history else []
    context_text = "\n".join(
        [f"{m['role'].upper()}: {m['content']}" for m in recent_context]
    )

    classifier_prompt = f"""
Analyze the conversation and the user's latest message to decide if the admin should be notified right now.

Notify admin (notify_admin = true) ONLY when:
1. The user asks for payment details (card number, Sberbank, crypto wallet, USDT, how to pay) or confirms readiness to pay for a specific choice.
2. The user explicitly asks to connect/speak with an admin or complains that an admin hasn't contacted them / is taking too long.

Do NOT notify admin (notify_admin = false) for:
- General greetings, price questions, or objections/discounts.
- Vague confirmation like "ok / xo'p" when the chosen account/balance or payment method hasn't been clarified yet.

Conversation history:
{context_text}

Latest user message:
{user_message}

Return ONLY valid JSON with keys:
"notify_admin": boolean,
"reason": "payment_request" | "admin_escalation" | "none",
"summary": "short 1-line summary in Uzbek of what user wants"
"""

    try:
        res = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": classifier_prompt}],
            temperature=0.1,
            max_tokens=180
        )
        raw = res.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:].strip()
        data = json.loads(raw)
        return {
            "notify_admin": bool(data.get("notify_admin", False)),
            "reason": str(data.get("reason", "none")),
            "summary": str(data.get("summary", user_message))
        }
    except Exception as e:
        logger.warning(f"Intent classifier fallback: {e}")
        lower_msg = user_message.lower()
        keywords = [
            "карта", "karta", "card", "реквизит", "rekvizit", "crypto", "крипта",
            "trc20", "bep20", "usdt", "номер карты", "karta raqami", "to'lov",
            "оплата", "payment", "сбер", "humo", "uzcard", "admin", "админ",
            "bog'lan", "xabar ber", "kut"
        ]
        matched = any(word in lower_msg for word in keywords)
        return {
            "notify_admin": matched,
            "reason": "payment_request" if matched else "none",
            "summary": user_message
        }


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Assalomu alaykum! / Здравствуйте! / Hello!\n\n"
        "Demo hisob bo'yicha maslahatchiman. Istalgan tilda yozing — oldingi gaplarni eslab qolgan holda, aynan siz yozgan tilda javob beraman!\n"
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

    try:
        intent = await analyze_intent_and_handoff(history, user_message)

        handoff_note = ""
        if intent["notify_admin"]:
            if intent["reason"] == "admin_escalation":
                handoff_note = (
                    "\n[Internal note: The user says the admin hasn't replied yet or is waiting. "
                    "Acknowledge empathetically in the user's language, confirm the urgency is being passed to the admin, "
                    "and ask briefly for patience without closing the conversation abruptly.]"
                )
            else:
                handoff_note = (
                    "\n[Internal note: The user is asking about payment or details. "
                    "Before ending, clarify/confirm the exact platform, balance, and payment method (Uzcard/Humo, Sberbank, or USDT TRC20/BEP20) "
                    "if not yet clear, and let them know payment details/admin follow-up are being arranged in their language.]"
                )

        current_prompt = (
            f"LATEST USER MESSAGE: \"{user_message}\"\n"
            f"INSTRUCTION: Understand context from chat history above, "
            f"reply strictly in the language of the LATEST USER MESSAGE above, "
            f"use 'million' instead of 'M' when replying in Uzbek, "
            f"clarify details smoothly instead of ending abruptly, and provide exact UZS/RUB/KZT prices when relevant."
            f"{handoff_note}"
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

        # Adminga xabar yuborish (ketma-ket takrorlanmasligi uchun 45 soniya oraliq)
        now = time.time()
        last_notify_time = context.user_data.get("last_admin_notify_time", 0)
        last_notify_reason = context.user_data.get("last_admin_notify_reason", "")

        should_send_now = intent["notify_admin"] and (
            now - last_notify_time > 45 or intent["reason"] != last_notify_reason
        )

        if should_send_now:
            try:
                title = (
                    "⏳ ADMIN BILAN BOG'LANISH / KUTISH SO'ROVI!"
                    if intent["reason"] == "admin_escalation"
                    else "💳 TO'LOV / REKVIZIT SO'ROVI!"
                )
                notify = (
                    f"{title}\n\n"
                    f"👤 {update.effective_user.full_name}\n"
                    f"🆔 {update.effective_user.id}\n"
                    f"🔗 @{update.effective_user.username or 'yo‘q'}\n"
                    f"📌 Xulosa: {intent['summary']}\n\n"
                    f"💬 Xabar: {user_message}"
                )
                await context.bot.send_message(chat_id=ADMIN_ID, text=notify)
                context.user_data["last_admin_notify_time"] = now
                context.user_data["last_admin_notify_reason"] = intent["reason"]
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
