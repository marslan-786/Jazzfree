import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import aiohttp

numbers = ["03003143141", "03299202072"]

calling_task = None
session = None  # global aiohttp session

async def call_api(msisdn):
    url = f"https://data-api.impossible-world.xyz/api/activate?msisdn={msisdn}"
    try:
        async with session.get(url) as resp:
            text = await resp.text()
            print(f"[call_api] Called {msisdn}, response: {text[:100]}")  # limit print length
            return text
    except Exception as e:
        print(f"[call_api] Error calling {msisdn}: {e}")
        return f"Error: {e}"

async def caller(update, numbers):
    i = 0
    chat_id = update.effective_chat.id
    app = update.app

    print("[caller] Started caller task")
    while True:
        current_number = numbers[i % len(numbers)]
        print(f"[caller] Calling number: {current_number}")
        response = await call_api(current_number)
        try:
            await app.bot.send_message(chat_id, f"Called {current_number}:\nResponse: {response}")
            print(f"[caller] Sent message for {current_number}")
        except Exception as e:
            print(f"[caller] Error sending message: {e}")
        i += 1
        await asyncio.sleep(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global calling_task, session
    if calling_task and not calling_task.done():
        await update.message.reply_text("Already started calling.")
        return

    if session is None:
        session = aiohttp.ClientSession()

    await update.message.reply_text("Starting to call API alternately on the numbers...")
    print("[start] Starting caller task")

    calling_task = asyncio.create_task(caller(update, numbers))

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global calling_task, session
    if not calling_task or calling_task.done():
        await update.message.reply_text("Already stopped.")
        return

    calling_task.cancel()
    try:
        await calling_task
    except asyncio.CancelledError:
        print("[stop] Caller task cancelled")
        pass

    if session:
        await session.close()
        session = None
        print("[stop] HTTP session closed")

    await update.message.reply_text("Stopped calling the API.")

if __name__ == "__main__":
    TOKEN = "7902248899:AAHElm3aHJeP3IZiy2SN3jLAgV7ZwRXnvdo"
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))

    print("Bot is running...")
    app.run_polling()