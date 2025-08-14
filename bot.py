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
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global variables
channels = [
    {"name": "Impossible", "link": "https://t.me/only_possible_world", "id": "-1002650289632"},
    {"name": "Kami Broken", "link": "https://t.me/kami_broken5"},
    {"name": "Sudais Ahmed", "link": "http://t.me/sudais_ahmed"},
    {"name": "JND TECH", "link": "https://t.me/jndtech1"},
    {"name": "SYBER EXPERT", "link": "https://t.me/CRACKEDEVER"}
]

user_states = {}
user_cancel_flags = {}
active_claim_tasks = {}
blocked_numbers = set()
activated_numbers = set()
request_count = 5
requests_enabled = True
session = None

# --------- SESSION MANAGEMENT ----------
async def init_session():
    global session
    session = aiohttp.ClientSession(headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json"
    })

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
        await msg.edit_text(text, **kwargs)
    except Forbidden:
        logger.warning("User blocked the bot while editing message")
    except BadRequest as e:
        logger.error(f"BadRequest: {e}")

# --------- API CALL ----------
async def fetch_json(url):
    global session
    if session is None or session.closed:
        await init_session()

    try:
        async with session.get(url, timeout=10) as resp:
            return await resp.json()
    except Exception as e:
        return {"status": False, "message": f"Request failed: {e}"}

# --------- COMMAND HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_buttons = []
    for i in range(0, len(channels), 2):
        row = [InlineKeyboardButton(ch["name"], url=ch["link"]) for ch in channels[i:i+2]]
        channel_buttons.append(row)

    channel_buttons.append([InlineKeyboardButton("I have joined", callback_data="joined")])

    await safe_reply(
        update.message,
        "Welcome! Please join the channels below and then press 'I have joined':",
        reply_markup=InlineKeyboardMarkup(channel_buttons)
    )

async def check_membership(user_id, channel_id, context):
    if not channel_id:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Error checking membership: {e}")
        return False

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    try:
        await query.answer()
    except Exception as e:
        logger.error(f"Callback answer error: {e}")

    if query.data == "joined":
        # Check if user has joined all channels
        all_joined = True
        for ch in channels:
            if ch.get("id"):
                if not await check_membership(user_id, ch["id"], context):
                    all_joined = False
                    await safe_edit(query, f"Please join the channel: {ch['name']} first.")
                    break

        if all_joined:
            keyboard = [
                [InlineKeyboardButton("Login", callback_data="login")],
                [InlineKeyboardButton("Claim Your MB", callback_data="claim_menu")]
            ]
            await safe_edit(
                query,
                "You have joined all required channels. Please choose an option:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif query.data == "login":
        user_states[user_id] = {"stage": "awaiting_phone_for_login"}
        await safe_edit(query, "Please send your phone number to receive OTP (e.g., 03012345678):")

    elif query.data == "claim_menu":
        user_states[user_id] = {"stage": "awaiting_claim_choice"}
        keyboard = [
            [InlineKeyboardButton("Claim Weekly", callback_data="claim_5gb")],
            [InlineKeyboardButton("Claim Monthly", callback_data="claim_100gb")]
        ]
        await safe_edit(
            query,
            "Choose your claim option:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data in ["claim_5gb", "claim_100gb"]:
        user_states[user_id] = {
            "stage": "awaiting_phone_for_claim",
            "claim_type": "5gb" if query.data == "claim_5gb" else "100gb"
        }
        await safe_edit(query, "Please send the phone number on which you want to activate your claim:")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.message.from_user.id
    text = update.message.text.strip()
    state = user_states.get(user_id, {})

    if not requests_enabled:
        await safe_reply(update.message, "⚠️ Requests are currently disabled.")
        return

    # Handle different states
    if state.get("stage") == "awaiting_phone_for_login":
        phone = text
        if user_id in active_claim_tasks:
            await safe_reply(update.message, "⏳ Login process already running.")
            return
        
        async def login_task():
            while True:
                if user_cancel_flags.get(user_id, False):
                    await safe_reply(update.message, "🛑 Process stopped.")
                    user_cancel_flags[user_id] = False
                    break
                
                data = await fetch_json(f"https://data-api.impossible-world.xyz/api/log?num={phone}")
                msg = (data.get("message") or "").lower()
                
                if "otp successfully generated" in msg:
                    user_states[user_id] = {"stage": "awaiting_otp", "phone": phone}
                    await safe_reply(update.message, "✅ OTP sent successfully, please enter the OTP.")
                    break
                elif "pin not allowed" in msg:
                    user_states[user_id] = {"stage": "logged_in", "phone": phone}
                    await safe_reply(
                        update.message,
                        "ℹ️ Number already verified.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📦 Claim Your MB", callback_data="claim_menu")]])
                    )
                    break
                else:
                    await asyncio.sleep(2)

        task = asyncio.create_task(login_task())
        active_claim_tasks[user_id] = task
        task.add_done_callback(lambda _: active_claim_tasks.pop(user_id, None))
        await safe_reply(update.message, "🔄 Login process started!")

    elif state.get("stage") == "awaiting_otp":
        phone = state.get("phone")
        otp = text
        
        async def otp_task():
            while True:
                if user_cancel_flags.get(user_id, False):
                    await safe_reply(update.message, "🛑 Process stopped.")
                    user_cancel_flags[user_id] = False
                    break
                
                data = await fetch_json(f"https://data-api.impossible-world.xyz/api/log?num={phone}&otp={otp}")
                msg = (data.get("message") or "").lower()
                
                if "otp verified" in msg or "success" in msg:
                    user_states[user_id] = {"stage": "logged_in", "phone": phone}
                    await safe_reply(
                        update.message,
                        "✅ OTP verified successfully!",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📦 Claim Your MB", callback_data="claim_menu")]])
                    )
                    break
                elif "wrong otp" in msg or "invalid otp" in msg:
                    await safe_reply(update.message, "❌ Wrong OTP, please try again.")
                    break
                else:
                    await asyncio.sleep(2)

        task = asyncio.create_task(otp_task())
        active_claim_tasks[user_id] = task
        task.add_done_callback(lambda _: active_claim_tasks.pop(user_id, None))
        await safe_reply(update.message, "🔄 Verifying OTP...")

    elif state.get("stage") == "awaiting_phone_for_claim":
        phones = text.split()
        valid_phones = [p for p in phones if p.isdigit() and len(p) >= 10]

        if not valid_phones:
            await safe_reply(update.message, "⚠️ Please enter valid phone numbers")
            return

        if user_id in active_claim_tasks:
            await safe_reply(update.message, "⚠️ Claim process already running")
            return

        claim_type = state.get("claim_type", "5gb")
        task = asyncio.create_task(handle_claim_process(update.message, user_id, valid_phones, claim_type))
        active_claim_tasks[user_id] = task
        task.add_done_callback(lambda _: active_claim_tasks.pop(user_id, None))
        await safe_reply(update.message, "⏳ Claim process started!")

    else:
        await safe_reply(update.message, "ℹ️ Please use /start")

async def handle_claim_process(message, user_id, phones, claim_type):
    for phone in phones:
        for i in range(1, request_count + 1):
            if user_cancel_flags.get(user_id, False):
                await safe_reply(message, "🛑 Process stopped by user.")
                user_cancel_flags[user_id] = False
                return

            url = (
                f"https://data-api.impossible-world.xyz/api/act?number={phone}"
                if claim_type == "5gb"
                else f"https://data-api.impossible-world.xyz/api/acti?number={phone}"
            )

            try:
                data = await fetch_json(url)
                msg = (data.get("message") or "").lower()
                
                if "success" in msg or "activated" in msg:
                    await safe_reply(message, f"[{phone}] Request {i}: ✅ Success")
                    activated_numbers.add(phone)
                else:
                    await safe_reply(message, f"[{phone}] Request {i}: ❌ {msg}")
                
                await asyncio.sleep(0.5)
            except Exception as e:
                await safe_reply(message, f"[{phone}] Request {i}: ❌ Error: {str(e)}")
                await asyncio.sleep(0.5)

    user_states[user_id] = {"stage": "logged_in"}

# --------- ADMIN COMMANDS ----------
async def set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global request_count
    try:
        count = int(context.args[0])
        if count < 1:
            raise ValueError
        request_count = count
        await update.message.reply_text(f"✅ Request count set to {count}")
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Usage: /set 5 (where 5 is the number of requests)")

async def turn_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global requests_enabled
    requests_enabled = True
    await update.message.reply_text("✅ Requests enabled")

async def turn_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global requests_enabled
    requests_enabled = False
    await update.message.reply_text("⛔ Requests disabled")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_text = (
        f"📊 Bot Status\n"
        f"🔹 Requests: {'✅ On' if requests_enabled else '⛔ Off'}\n"
        f"🔹 Request count: {request_count}\n"
        f"🔹 Blocked numbers: {len(blocked_numbers)}\n"
        f"🔹 Activated numbers: {len(activated_numbers)}\n"
        f"🔹 Active tasks: {len(active_claim_tasks)}"
    )
    await update.message.reply_text(status_text)

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_cancel_flags[user_id] = True
    await update.message.reply_text("🛑 Process stopped")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

# --------- MAIN FUNCTION ----------
async def run_bot(token):
    app = ApplicationBuilder().token(token).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CommandHandler("set", set_command))
    app.add_handler(CommandHandler("on", turn_on))
    app.add_handler(CommandHandler("off", turn_off))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_error_handler(error_handler)
    
    await app.initialize()
    await app.start()
    logger.info(f"Bot with token {token[-5:]} started successfully")
    return app

async def main():
    await init_session()
    
    TOKENS = [
            "8276543608:AAEbE-8J3ueGMAGQtWeedcMry3iDjAivG0U",
            "8224844544:AAFpI-iycJQCyzu0FAduPjn5ztos3Rylr3Q",
            "8356375247:AAH_EGWGTiouHMI0Ba-CkY66K4DXcBQPzVs",
            "8020275808:AAGWNYI4SPYJ2yQ_F7INbH8ZcwDuYPqil10",
            "8407271613:AAGSKdrwamP2GOKklg3_Be2xGQiNip5hVmw",
            "8403628798:AAHW3XuyMZpgfKt2mEJwS0tMTvTtoxSyhck",
            "7787284037:AAGWstgBGla0B06B_3Re1A6WJbux_703hgQ",
            "8335584448:AAGmW5n4_xwN9MfMeDL8jBMUsOBEMj42D7Y",
            "7459204571:AAEo-CD_K9FjOPiKdg3gXSvAOat55h37Y0Q",
    
    ]
    
    bots = []
    try:
        for token in TOKENS:
            try:
                bot = await run_bot(token)
                bots.append(bot)
            except Exception as e:
                logger.error(f"Failed to start bot with token {token[-5:]}: {e}")
        
        # Keep running
        while True:
            await asyncio.sleep(3600)
            
    except asyncio.CancelledError:
        pass
    finally:
        for bot in bots:
            await bot.stop()
            await bot.shutdown()
        await close_session()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")