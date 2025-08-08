# bot.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

import aiohttp
import asyncio
import re
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# state: None | "waiting_for_number"
user_state: dict[int, str | None] = {}

# Your external API (already returns JSON)
API_URL = "https://data-api.impossible-world.xyz/api/active?msisdn="


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start — show join buttons and 'I Joined'."""
    msg = "👋 Welcome!\n\nPlease join both channels to proceed:"
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel 1", url="https://t.me/only_possible_world")],
        [InlineKeyboardButton("📢 Join Channel 2", url="https://t.me/kami_broken5")],
        [InlineKeyboardButton("✅ I Joined", callback_data="joined")],
    ]
    await update.effective_message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses (joined / claim)."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_id = user.id

    if query.data == "joined":
        # (Optional) here you could check actual membership with get_chat_member if bot has privileges.
        keyboard = [[InlineKeyboardButton("📥 Claim Your MB", callback_data="claim")]]
        await query.message.reply_text(
            "🎉 Great! Click below to claim your MB.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif query.data == "claim":
        # mark user as ready to send number
        user_state[user_id] = "waiting_for_number"
        await query.message.reply_text(
            "📱 Please send your number (e.g., 03012345678) to claim your MB."
        )


def _normalize_msisdn(text: str) -> str | None:
    """Keep only digits and normalize to 03XXXXXXXXX (11 digits) format.
       Accepts: 03012345678 or 923012345678 and converts latter to 03012345678.
    """
    digits = re.sub(r"\D", "", text)
    if digits.startswith("92") and len(digits) == 12:
        return "0" + digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        return digits
    return None


async def number_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages — expect the number only when user clicked 'claim' first."""
    message = update.effective_message
    if not message or not message.text:
        return

    user = update.effective_user
    user_id = user.id
    text = message.text.strip()

    # Ensure user clicked 'claim' first
    if user_state.get(user_id) != "waiting_for_number":
        await message.reply_text("❌ Please click '📥 Claim Your MB' first.")
        return

    msisdn = _normalize_msisdn(text)
    if not msisdn:
        await message.reply_text(
            "❌ Invalid number format.\nSend like: `03012345678` or `923012345678`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Call external API (GET)
    try:
        async with aiohttp.ClientSession() as session:
            url = API_URL + msisdn
            logger.info("Calling external API: %s", url)
            async with session.get(url, timeout=20) as resp:
                content_type = resp.headers.get("Content-Type", "")
                text_resp = await resp.text()

                # Try parse JSON first
                data = None
                if "application/json" in content_type:
                    try:
                        data = json.loads(text_resp)
                    except Exception:
                        data = None
                else:
                    # Sometimes server returns JSON but wrong content-type — try to load anyway
                    try:
                        data = json.loads(text_resp)
                    except Exception:
                        data = None

                if data is None:
                    # fallback — put the raw HTML/text into message field
                    data = {"status": "unknown", "message": text_resp, "offer": "Unknown", "msisdn": msisdn}

        # Build user-friendly reply (HTML)
        status = data.get("status", "").lower()
        if status == "success" or status.startswith("success"):
            reply = (
                f"✅ <b>Request Successful!</b>\n\n"
                f"📱 <b>Number:</b> {data.get('msisdn', msisdn)}\n"
                f"📶 <b>Offer:</b> {data.get('offer','5GB')}\n"
                f"💬 <b>Message:</b> {data.get('message','')}"
            )
        else:
            # if server returned HTML or unknown, print a helpful box
            reply = (
                f"❌ <b>Failed / Unknown response</b>\n\n"
                f"📱 <b>Number:</b> {msisdn}\n"
                f"💬 <pre>{data.get('message', '')[:800]}</pre>"
            )

    except asyncio.TimeoutError:
        logger.exception("Timeout calling external API")
        reply = "⚠️ Request timed out. Please try again later."
    except Exception as e:
        logger.exception("Error calling external API")
        reply = f"⚠️ Error: {e}"

    # send reply and reset user state
    await message.reply_text(reply, parse_mode=ParseMode.HTML)
    user_state[user_id] = None


async def error_handler(update: Update | None, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler — logs and notifies user (if possible)."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text("⚠️ An internal error occurred. Please try again later.")
    except Exception:
        pass


def main():
    # <-- PUT YOUR BOT TOKEN HERE (do NOT share it publicly) -->
    BOT_TOKEN = "8276543608:AAEbE-8J3ueGMAGQtWeedcMry3iDjAivG0U"

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, number_handler))

    app.add_error_handler(error_handler)

    print("🤖 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()