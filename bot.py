import aiohttp
import asyncio
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden, BadRequest
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

channels = [
    {"name": "Impossible", "link": "https://t.me/only_possible_world", "id": "-1002650289632"},
    {"name": "Kami Broken", "link": "https://t.me/kami_broken5"}
]

user_states = {}
session: aiohttp.ClientSession = None  # global aiohttp session

# --------- SESSION MANAGEMENT ----------
async def start_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()

async def close_session():
    global session
    if session and not session.closed:
        await session.close()

# --------- SAFE MESSAGE SEND ----------
async def safe_reply(msg, text, **kwargs):
    try:
        await msg.reply_text(text, **kwargs)
    except Forbidden:
        logger.warning(f"User blocked the bot: {msg.chat_id}")
    except BadRequest as e:
        logger.error(f"BadRequest: {e}")

async def safe_edit(msg, text, **kwargs):
    try:
        await msg.edit_message_text(text, **kwargs)
    except Forbidden:
        logger.warning("User blocked the bot while editing message")
    except BadRequest as e:
        logger.error(f"BadRequest: {e}")

# --------- API CALL ----------
async def fetch_json(url):
    global session
    if session is None or session.closed:
        await start_session()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    try:
        async with session.get(url, timeout=10, headers=headers) as resp:
            text = await resp.text()
            try:
                return await resp.json()
            except Exception as e:
                return {"status": False, "message": f"Response not JSON: {e}", "raw": text}
    except Exception as e:
        return {"status": False, "message": f"Request failed: {e}"}

# --------- COMMAND HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(ch["name"], url=ch["link"]) for ch in channels],
                [InlineKeyboardButton("I have joined", callback_data="claim_100gb")]]
    await safe_reply(update.message,
                     "Welcome! Please join the channels below and then press 'I have joined':",
                     reply_markup=InlineKeyboardMarkup(keyboard))

async def check_membership(user_id, channel_id, context):
    if not channel_id:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "joined":
        for ch in channels:
            if ch.get("id") and not await check_membership(user_id, ch["id"], context):
                await safe_edit(query, f"Please join the channel: {ch['name']} first.")
                return
        keyboard = [[InlineKeyboardButton("Claim Your MB", callback_data="claim_menu")]]
        await safe_edit(query, "You have joined all required channels. Please choose an option:",
                        reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "login":
        user_states[user_id] = {"stage": "awaiting_phone_for_login"}
        await safe_edit(query, "Please send your phone number to receive OTP (e.g., 03012345678):")

    elif query.data == "claim_menu":
        user_states[user_id] = {"stage": "awaiting_claim_choice"}
        keyboard = [
            [InlineKeyboardButton("Claim 5 GB", callback_data="claim_5gb")],
            [InlineKeyboardButton("Claim 100 GB", callback_data="claim_100gb")]
        ]
        await safe_edit(query, "Choose your claim option:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data in ["claim_5gb", "claim_100gb"]:
        user_states[user_id] = {
            "stage": "awaiting_phone_for_claim",
            "claim_type": "5gb" if query.data == "claim_5gb" else "100gb"
        }
        await safe_edit(query, "Please send the phone number on which you want to activate your claim:")

# --- Default config ---
request_count = 5  # Global API calls count

async def set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global request_count
    try:
        count = int(context.args[0])
        if count < 1:
            raise ValueError
        request_count = count
        await update.message.reply_text(f"✅ اب سے تمام یوزرز کے لیے API کالز کی تعداد {count} مقرر کر دی گئی ہے۔")
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ صحیح استعمال: /set 5 (جہاں 5 کالز کی تعداد ہے)")

# Global activated numbers set
activated_numbers = set()

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global request_count
    if not update.message:
        return

    user_id = update.message.from_user.id
    text = update.message.text
    state = user_states.get(user_id, {})

    # --- LOGIN PHONE ---
    if state.get("stage") == "awaiting_phone_for_login":
        phone = text.strip()
        data = await fetch_json(f"https://data-api.impossible-world.xyz/api/login?msisdn={phone}")
        if data.get("status"):
            user_states[user_id] = {"stage": "awaiting_otp", "phone": phone}
            await safe_reply(update.message, "📲 OTP بھیج دیا گیا ہے! براہ کرم اپنا 4 ہندسوں کا OTP درج کریں۔")
        else:
            await safe_reply(update.message, "❌ OTP بھیجنے میں ناکامی۔ براہ کرم دوبارہ کوشش کریں۔")

    # --- LOGIN OTP ---
    elif state.get("stage") == "awaiting_otp":
        otp = text.strip()
        phone = state.get("phone")
        data = await fetch_json(f"https://data-api.impossible-world.xyz/api/login?msisdn={phone}&otp={otp}")
        if data.get("status"):
            user_states[user_id] = {"stage": "logged_in", "phone": phone}
            await safe_reply(
                update.message,
                "✅ OTP کامیابی سے تصدیق ہوگیا! اب آپ اپنا MB کلیم کر سکتے ہیں۔",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📦 Claim Your MB", callback_data="claim_menu")]])
            )
        else:
            await safe_reply(update.message, "❌ غلط OTP۔ براہ کرم دوبارہ کوشش کریں۔")

    # --- CLAIM ---
    elif state.get("stage") == "awaiting_phone_for_claim":
        phone = text.strip()

        # پہلے چیک کریں کہ نمبر پہلے activate ہوا ہے یا نہیں
        if phone in activated_numbers:
            await safe_reply(update.message, "⚠️ بھائی، آپ پہلے ہی اس نمبر پر پیکج کامیابی سے لگا چکے ہیں۔ دوبارہ کوشش نہ کریں۔")
            return

        url = (
            f"https://data-api.impossible-world.xyz/api/active?msisdn={phone}"
            if state.get("claim_type") == "5gb"
            else f"https://data-api.impossible-world.xyz/api/activate?msisdn={phone}"
        )

        package_activated = False
        success_count = 0  # کامیاب ریکویسٹز کا شمار

        for i in range(1, request_count + 1):
            resp = await fetch_json(url)

            if isinstance(resp, dict):
                msg = str(resp.get("message", "")).lower()
                if "successfully received" in msg:
                    package_activated = True
                    success_count += 1
                    await safe_reply(update.message, f"📨 ریکویسٹ {i}: ✅ کامیاب! آپ کا پیکج ایکٹیویٹ ہو چکا ہے۔")
                    if success_count >= 3:
                        await safe_reply(update.message, "📢 بھائی آپ نے تین بار پیکج کامیابی سے حاصل کر لیا ہے، مزید کوشش نہ کریں۔")
                        break  # 3 کامیابیوں کے بعد loop ختم کریں
                elif "no message" in msg or "server down" in msg:
                    await safe_reply(update.message, f"📨 ریکویسٹ {i}: ❌ پیکج ایکٹیویٹ نہیں ہوا۔")
                else:
                    await safe_reply(update.message, f"📨 ریکویسٹ {i}: ❌ پیکج ایکٹیویٹ نہیں ہوا۔")
            else:
                await safe_reply(update.message, f"📨 ریکویسٹ {i}: ❌ API ایرر: {resp}")

            await asyncio.sleep(5)  # ہر ریکویسٹ کے بعد 5 سیکنڈ کا وقفہ

        if package_activated:
            activated_numbers.add(phone)  # نمبر محفوظ کریں

        if not package_activated:
            await safe_reply(update.message, "❌ تمام کوششوں کے باوجود پیکج ایکٹیویٹ نہیں ہوا، براہ کرم دوبارہ کوشش کریں۔")

        user_states[user_id] = {"stage": "logged_in", "phone": phone}

    else:
        await safe_reply(update.message, "ℹ️ براہ کرم /start استعمال کریں۔")

# --------- ERROR HANDLER ----------
async def error_handler(update, context):
    logger.error(f"Update {update} caused error {context.error}")

# --------- STARTUP / SHUTDOWN ----------
async def on_startup(app):
    await start_session()

async def on_shutdown(app):
    await close_session()

# --------- MAIN ----------
if __name__ == "__main__":
    app = ApplicationBuilder().token("8276543608:AAEbE-8J3ueGMAGQtWeedcMry3iDjAivG0U") \
        .post_init(on_startup).post_shutdown(on_shutdown).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("set", set_command))
    
    print("Bot is running...")
    app.run_polling()