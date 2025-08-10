from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
import requests

# چینلز کی تفصیل
channels = [
    {"name": "Impossible", "link": "https://t.me/only_possible_world", "id": "-1002650289632"},
    {"name": "Kami Broken", "link": "https://t.me/kami_broken5"}
]

user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    row = []
    # چینلز کو ایک لائن میں بٹن کے طور پر دکھائیں
    for ch in channels:
        row.append(InlineKeyboardButton(ch["name"], url=ch["link"]))
    keyboard.append(row)
    # I have joined کا بٹن نیچے
    keyboard.append([InlineKeyboardButton("I have joined", callback_data="joined")])
    
    await update.message.reply_text(
        "Welcome! Please join the channels below and then press 'I have joined':",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def check_membership(user_id, channel_id, context):
    # صرف اسی چینل میں ممبر چیک کرنا ہے جس کی ID دی گئی ہے
    if not channel_id:
        return True  # اگر ID نہیں ہے تو سکپ کر دو (یعنی assume joined)
    try:
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except:
        pass
    return False

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "joined":
        # چیک کریں کہ یوزر نے جس چینلز کو join کیا ہے
        for ch in channels:
            channel_id = ch.get("id")
            joined = await check_membership(user_id, channel_id, context)
            if channel_id and not joined:
                await query.edit_message_text(f"Please join the channel: {ch['name']} first.")
                return
        # اگر سب چینلز جوائن ہیں یا جس چینل کی ID نہیں ہے اس میں چیک نہیں کرنا تو آگے بڑھائیں
        keyboard = [
            [InlineKeyboardButton("Claim Your MB", callback_data="claim_100gb")]
        ]
        await query.edit_message_text("You have joined all required channels. Please choose an option:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "login":
        user_states[user_id] = {"stage": "awaiting_phone_for_login"}
        await query.edit_message_text("Please send your phone number to receive OTP (e.g., 03012345678):")

    elif query.data == "claim_menu":
        user_states[user_id] = {"stage": "awaiting_claim_choice"}
        keyboard = [
            [InlineKeyboardButton("Claim 5 GB", callback_data="claim_5gb")],
            [InlineKeyboardButton("Claim 100 GB", callback_data="claim_100gb")]
        ]
        await query.edit_message_text("Choose your claim option:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data in ["claim_5gb", "claim_100gb"]:
        claim_type = "5gb" if query.data == "claim_5gb" else "100gb"
        user_states[user_id] = {"stage": "awaiting_phone_for_claim", "claim_type": claim_type}
        await query.edit_message_text("Please send the phone number on which you want to activate your claim:")

import json

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:  # اگر message ہی نہیں ہے
        return

    user_id = update.message.from_user.id
    text = update.message.text
    state = user_states.get(user_id, {})

    if state.get("stage") == "awaiting_phone_for_login":
        phone = text.strip()
        url = f"https://data-api.impossible-world.xyz/api/login?msisdn={phone}"
        try:
            response = requests.get(url)
            data = response.json()
            if data.get("status") == True:
                user_states[user_id] = {"stage": "awaiting_otp", "phone": phone}
                await update.message.reply_text("OTP successfully sent! Please enter your 4-digit OTP:")
            else:
                error_msg = data.get("message", "Failed to send OTP. Please try again.")
                await update.message.reply_text(error_msg)
        except Exception:
            await update.message.reply_text("Failed to send OTP. Please try again.")

    elif state.get("stage") == "awaiting_otp":
        otp = text.strip()
        phone = state.get("phone")
        url = f"https://data-api.impossible-world.xyz/api/login?msisdn={phone}&otp={otp}"
        try:
            response = requests.get(url)
            data = response.json()
            if data.get("status") == True:
                user_states[user_id] = {"stage": "logged_in", "phone": phone}
                keyboard = [
                    [InlineKeyboardButton("Claim Your MB", callback_data="claim_menu")]
                ]
                await update.message.reply_text(
                    "OTP verified successfully! You can now claim your MB.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                error_msg = data.get("message", "Invalid OTP. Please try again.")
                await update.message.reply_text(error_msg)
        except Exception:
            await update.message.reply_text("Invalid OTP. Please try again.")

    elif state.get("stage") == "awaiting_phone_for_claim":
        phone = text.strip()
        claim_type = state.get("claim_type")

        if claim_type == "5gb":
            url = f"https://data-api.impossible-world.xyz/api/active?msisdn={phone}"
        else:
            url = f"https://data-api.impossible-world.xyz/api/activate?msisdn={phone}"

        responses = []
        for i in range(5):  # پانچ بار API کال کریں
            try:
                response = requests.get(url)
                data = response.json()
                responses.append(data)
            except Exception:
                responses.append({"status": False, "message": "Request failed."})

        import json
        responses_text = "\n\n".join([json.dumps(resp, indent=2) for resp in responses])

        await update.message.reply_text(f"Responses from 5 API calls:\n\n{responses_text}")

        user_states[user_id] = {"stage": "logged_in", "phone": phone}

    else:
        await update.message.reply_text("Please use /start to begin.")

if __name__ == "__main__":
    app = ApplicationBuilder().token("8276543608:AAEbE-8J3ueGMAGQtWeedcMry3iDjAivG0U").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))

    print("Bot is running...")
    app.run_polling()