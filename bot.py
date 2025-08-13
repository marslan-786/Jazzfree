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
user_cancel_flags = {}

# global flag for enabling/disabling requests
requests_enabled = True  # فرض کریں یہ کہیں globally defined ہے

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global request_count, requests_enabled
    if not update.message:
        return

    user_id = update.message.from_user.id
    text = update.message.text
    state = user_states.get(user_id, {})

    # سب سے پہلے چیک کرو کہ requests_enabled ہے یا نہیں
    if not requests_enabled:
        await safe_reply(update.message, "⚠️ معذرت! API ریکویسٹز اس وقت بند ہیں۔ براہ کرم بعد میں کوشش کریں۔")
        return

    # --- LOGIN PHONE ---
    if state.get("stage") == "awaiting_phone_for_login":
        phone = text.strip()
        data = await fetch_json(f"https://data-api.impossible-world.xyz/api/login?number={phone}")
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

    # --- CLAIM MULTIPLE NUMBERS SUPPORTED ---
    elif state.get("stage") == "awaiting_phone_for_claim":
        phones = text.strip().split()
        valid_phones = [p for p in phones if p.isdigit() and len(p) >= 10]

        if not valid_phones:
            await safe_reply(update.message, "⚠️ براہ کرم درست نمبر درج کریں (مثال: 03001234567 03007654321)")
            return

        already_activated = [p for p in valid_phones if p in activated_numbers]
        if already_activated:
            await safe_reply(update.message, f"⚠️ یہ نمبر پہلے ہی ایکٹیویٹ ہو چکے ہیں: {', '.join(already_activated)}")
            valid_phones = [p for p in valid_phones if p not in activated_numbers]

        if not valid_phones:
            return

        package_activated_any = False
        success_counts = {p: 0 for p in valid_phones}

        for i in range(1, request_count + 1):
            if user_cancel_flags.get(user_id, False):
                await safe_reply(update.message, "🛑 آپ کی ریکویسٹز روک دی گئی ہیں۔")
                user_cancel_flags[user_id] = False
                break

            for phone in list(valid_phones):
                url = (
                    f"https://data-api.impossible-world.xyz/api/active?msisdn={phone}"
                    if state.get("claim_type") == "5gb"
                    else f"https://data-api.impossible-world.xyz/api/activate?number={phone}"
                )

                resp = await fetch_json(url)

                if isinstance(resp, dict):
                    status_text = resp.get("status", "❌ کوئی اسٹیٹس موصول نہیں ہوا")
                    await safe_reply(update.message, f"[{phone}] ریکویسٹ {i}: {status_text}")

                    if "success" in status_text.lower() or "activated" in status_text.lower():
                        package_activated_any = True
                        success_counts[phone] += 1
                        if success_counts[phone] >= 3:
                            await safe_reply(update.message, f"[{phone}] تین بار کامیابی حاصل ہو چکی ہے، مزید کوشش نہیں ہوگی۔")
                            valid_phones.remove(phone)
                            continue
                else:
                    await safe_reply(update.message, f"[{phone}] ریکویسٹ {i}: ❌ API ایرر: {resp}")

                await asyncio.sleep(2)

            if not valid_phones:
                break

            await asyncio.sleep(3)

        for phone, count in success_counts.items():
            if count > 0:
                activated_numbers.add(phone)

        if not package_activated_any:
            await safe_reply(update.message, "❌ کوئی بھی پیکج ایکٹیویٹ نہیں ہوا، براہ کرم دوبارہ کوشش کریں۔")

        user_states[user_id] = {"stage": "logged_in"}

    else:
        await safe_reply(update.message, "ℹ️ براہ کرم /start استعمال کریں۔")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_cancel_flags[user_id] = True  # cancel the ongoing requests for this user
    user_states.pop(user_id, None)      # optional: clear user state
    await update.message.reply_text("🚫 آپ کا سیشن فوراً روک دیا گیا ہے۔ اگر دوبارہ شروع کرنا چاہیں تو /start لکھیں۔")

# Global flag
requests_enabled = True

async def turn_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global requests_enabled
    requests_enabled = True
    await update.message.reply_text("✅ API ریکویسٹز اب فعال ہیں۔")

async def turn_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global requests_enabled
    requests_enabled = False
    await update.message.reply_text("⛔ API ریکویسٹز اب بند ہیں۔ براہ کرم بعد میں کوشش کریں۔")

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
    app = ApplicationBuilder().token("8201371529:AAFRNYxETgkzZVm6jQcC0tJqjG3CCeZvmWY") \
        .post_init(on_startup).post_shutdown(on_shutdown).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("set", set_command))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("on", turn_on))
    app.add_handler(CommandHandler("off", turn_off))
    
    print("Bot is running...")
    app.run_polling()