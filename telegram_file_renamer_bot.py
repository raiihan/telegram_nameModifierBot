import os
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import subprocess

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

SETTINGS_FILE = "settings.json"

# Load settings from file
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {"prefix": "", "suffix": "", "approved_users": [OWNER_ID], "convert_mkv": False}

# Save settings to file
def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text("Welcome! Send me any file to rename it.")

# Command: /setprefix
async def set_prefix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    prefix = ' '.join(context.args)
    settings = load_settings()
    settings["prefix"] = prefix
    save_settings(settings)
    await update.message.reply_text(f"Prefix set to: {prefix}")

# Command: /setsuffix
async def set_suffix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    suffix = ' '.join(context.args)
    settings = load_settings()
    settings["suffix"] = suffix
    save_settings(settings)
    await update.message.reply_text(f"Suffix set to: {suffix}")

# Command: /toggleconversion
async def toggle_conversion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    settings = load_settings()
    settings["convert_mkv"] = not settings.get("convert_mkv", False)
    save_settings(settings)
    status = "enabled" if settings["convert_mkv"] else "disabled"
    await update.message.reply_text(f"MKV conversion is now {status}.")

# Command: /approve
async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if context.args:
        try:
            uid = int(context.args[0])
            settings = load_settings()
            if uid not in settings["approved_users"]:
                settings["approved_users"].append(uid)
                save_settings(settings)
                await update.message.reply_text(f"User {uid} approved.")
        except:
            await update.message.reply_text("Invalid user ID.")

# Helper: Check if user is approved
def is_approved(user_id):
    settings = load_settings()
    return user_id in settings["approved_users"]

# Helper: Convert MKV to MP4 using ffmpeg subprocess
def convert_mkv_to_mp4(input_path, output_path):
    try:
        subprocess.run(["ffmpeg", "-i", input_path, "-c", "copy", output_path], check=True)
        return True
    except Exception as e:
        print("Conversion failed:", e)
        return False

# File receiver
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_approved(update.effective_user.id):
        return await update.message.reply_text("You're not approved to use this bot.")
    file = update.message.document or update.message.video
    if file:
        context.user_data['file'] = file
        await update.message.reply_text("Send the new name (without extension):")

# File renamer
async def rename_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_approved(update.effective_user.id):
        return
    if 'file' not in context.user_data:
        return
    file = context.user_data.pop('file')
    new_name = update.message.text.strip()
    settings = load_settings()
    prefix = settings.get("prefix", "")
    suffix = settings.get("suffix", "")
    convert_mkv = settings.get("convert_mkv", False)
    file_ext = os.path.splitext(file.file_name)[1]
    final_name = f"{prefix}{new_name}{suffix}{file_ext}"

    tg_file = await file.get_file()
    downloaded_path = await tg_file.download_to_drive(file.file_name)

    if file_ext.lower() == ".mkv" and convert_mkv:
        converted_name = final_name.replace(".mkv", ".mp4")
        converted_path = downloaded_path.replace(".mkv", ".mp4")
        if convert_mkv_to_mp4(downloaded_path, converted_path):
            await update.message.reply_document(open(converted_path, "rb"), filename=converted_name)
            os.remove(converted_path)
        else:
            await update.message.reply_text("Conversion failed. Sending original file.")
            await update.message.reply_document(open(downloaded_path, "rb"), filename=final_name)
        os.remove(downloaded_path)
    else:
        os.rename(downloaded_path, final_name)
        await update.message.reply_document(open(final_name, "rb"), filename=final_name)
        os.remove(final_name)

# Main
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setprefix", set_prefix))
    app.add_handler(CommandHandler("setsuffix", set_suffix))
    app.add_handler(CommandHandler("toggleconversion", toggle_conversion))
    app.add_handler(CommandHandler("approve", approve_user))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.Video.ALL, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), rename_file))

    print("Bot is running...")
    app.run_polling()

import asyncio

if __name__ == '__main__':
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except RuntimeError:
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.get_event_loop().run_until_complete(main())
