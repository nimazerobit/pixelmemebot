import os
import subprocess
from telegram import Update
from telegram.ext import ContextTypes
from core.config_loader import TEXTS

DOWNLOAD_DIR = "cache"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

MAX_DURATION = 300 # 5 minutes
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

async def convert_to_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    # must be a reply
    if not message.reply_to_message:
        await message.reply_text(TEXTS["convert_to_voice"]["help"], parse_mode="Markdown")
        return

    replied = message.reply_to_message

    # validate audio
    if replied.audio:
        duration = replied.audio.duration
        file_size = replied.audio.file_size
        file = await replied.audio.get_file()
        input_ext = ".mp3"
    elif replied.document and replied.document.mime_type and replied.document.mime_type.startswith("audio/"):
        duration = None
        file_size = replied.document.file_size
        file = await replied.document.get_file()
        input_ext = os.path.splitext(replied.document.file_name or "")[1]
    else:
        await message.reply_text(TEXTS["convert_to_voice"]["error_not_audio"], parse_mode="Markdown")
        return

    if duration and duration > MAX_DURATION:
        await message.reply_text(TEXTS["convert_to_voice"]["error_duration"], parse_mode="Markdown")
        return

    if file_size and file_size > MAX_FILE_SIZE:
        await message.reply_text(TEXTS["convert_to_voice"]["error_size"], parse_mode="Markdown")
        return

    input_path = os.path.join(DOWNLOAD_DIR, f"{file.file_id}{input_ext}")
    output_path = os.path.join(DOWNLOAD_DIR, f"{file.file_id}.ogg")

    try:
        # download
        await file.download_to_drive(input_path)

        # convert to telegram voice format
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", input_path,
                "-vn",
                "-ac", "1",
                "-ar", "48000",
                "-b:a", "64k",
                "-c:a", "libopus",
                "-application", "voip",
                output_path
            ],
            check=True,
            timeout=30
        )

        # send as voice
        with open(output_path, "rb") as voice:
            await message.reply_voice(voice=voice)

    except subprocess.TimeoutExpired:
        await message.reply_text(TEXTS["convert_to_voice"]["ffmpeg_timeout"])
    except subprocess.CalledProcessError:
        await message.reply_text(TEXTS["convert_to_voice"]["ffmpeg_failed"])
    finally:
        # cleanup
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)