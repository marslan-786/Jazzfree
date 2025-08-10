import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import aiohttp

# دو نمبر جن پر API کال کرنی ہے
numbers = ["03003143141", "03299202072"]  # دوسرا نمبر اپنی مرضی سے رکھ لو

# ایک فلیگ جو چیک کرے گا کہ کالنگ جاری ہے یا نہیں
calling = False

async def call_api(msisdn):
    url = f"https://data-api.impossible-world.xyz/api/activate?msisdn={msisdn}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                text = await resp.text()
                return text
        except Exception as e:
            return f"Error: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global calling
    if calling:
        await update.message.reply_text("Already started calling.")
        return
    calling = True
    await update.message.reply_text("Starting to call API alternately on the numbers...")
    
    i = 0
    while calling:
        current_number = numbers[i % len(numbers)]
        response = await call_api(current_number)
        await update.message.reply_text(f"Called {current_number}:\nResponse: {response}")
        i += 1
        await asyncio.sleep(5)  # 5 سیکنڈ انتظار کریں کالز کے بیچ، حسبِ ضرورت ایڈجسٹ کر لو

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global calling
    if not calling:
        await update.message.reply_text("Already stopped.")
        return
    calling = False
    await update.message.reply_text("Stopped calling the API.")

if __name__ == "__main__":
    import os
    TOKEN = os.getenv("7902248899:AAHElm3aHJeP3IZiy2SN3jLAgV7ZwRXnvdo")  # اپنا بوٹ ٹوکن یہاں رکھو یا environment variable میں رکھو
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    
    print("Bot is running...")
    app.run_polling()