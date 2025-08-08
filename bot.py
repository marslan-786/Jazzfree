import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

SEND_OTP_URL = "https://oopk.online/cyberghoost/index.php"
VERIFY_OTP_URL = "https://oopk.online/cyberghoost/index.php"
CLAIM_MB_URL = "https://data-api.impossible-world.xyz/api/active"

# /login command
async def login_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /login <phone>")
        return

    phone = context.args[0]
    try:
        requests.post(SEND_OTP_URL, data={"msisdn": phone})
        await update.message.reply_text(
            f"OTP has been sent to {phone}. Please verify using /verifyotp <phone> <otp>"
        )
    except Exception as e:
        await update.message.reply_text(f"Error sending OTP: {e}")

# /verifyotp command
async def verifyotp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /verifyotp <phone> <otp>")
        return

    phone = context.args[0]
    otp = context.args[1]
    phone_intl = phone.replace("0", "92", 1)

    try:
        res = requests.post(VERIFY_OTP_URL, data={"msisdn": phone_intl, "otp": otp})
        if "success" in res.text.lower():
            await update.message.reply_text("Login successful ✅")
        else:
            await update.message.reply_text("Invalid OTP ❌")
    except Exception as e:
        await update.message.reply_text(f"Error verifying OTP: {e}")

# /claim command
async def claim_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /claim <phone>")
        return

    phone = context.args[0]
    try:
        for _ in range(5):
            requests.get(f"{CLAIM_MB_URL}?msisdn={phone}")
        await update.message.reply_text("MB claimed successfully 🎉")
    except Exception as e:
        await update.message.reply_text(f"Error claiming MB: {e}")

def main():
    TOKEN = "8276543608:AAEbE-8J3ueGMAGQtWeedcMry3iDjAivG0U"  # Replace with your token
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("login", login_cmd))
    app.add_handler(CommandHandler("verifyotp", verifyotp_cmd))
    app.add_handler(CommandHandler("claim", claim_cmd))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()