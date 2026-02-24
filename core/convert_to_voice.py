import os
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, Application
from core.config_loader import TEXTS

# Configuration
DOWNLOAD_DIR = "cache"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
MAX_DURATION = 300  # 5 minutes
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# queue stores: (update, context, file_obj, input_ext, status_message)
conversion_queue = asyncio.Queue()
# waiting_users stores: {'chat_id': int, 'message_id': int} to update status
waiting_users = []

async def conversion_worker(app: Application):
    while True:
        update, context, file, input_ext, status_msg = await conversion_queue.get()

        try:
            # Remove current user from waiting list
            if waiting_users:
                waiting_users.pop(0)

            # Update current status
            await safe_edit(status_msg, TEXTS["convert_to_voice"]["processing"])

            # Update other users positions
            await update_queue_positions(app)

            await process_conversion(update, context, file, input_ext, status_msg)

        except Exception:
            await safe_edit(status_msg, TEXTS["convert_to_voice"]["failed"])

        finally:
            conversion_queue.task_done()

async def update_queue_positions(bot):
    # Updates the queue position message for all currently waiting users
    current_waiting = list(waiting_users)
    
    for i, user_data in enumerate(current_waiting):
        position = i + 1
        try:
            await bot.edit_message_text(
                chat_id=user_data['chat_id'],
                message_id=user_data['message_id'],
                text=TEXTS["convert_to_voice"]["added_to_queue"].format(position=position)
            )
        except Exception:
            pass

async def safe_edit(message, text):
    try:
        await message.edit_text(text)
    except Exception:
        pass

async def process_conversion(update, context, file_obj, input_ext, status_msg):
    # download -> convert -> send the voice
    input_path = os.path.join(DOWNLOAD_DIR, f"{file_obj.file_id}{input_ext}")
    output_path = os.path.join(DOWNLOAD_DIR, f"{file_obj.file_id}.ogg")

    try:
        # download
        await file_obj.download_to_drive(input_path)
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-vn",
            "-ac", "1",
            "-ar", "48000",
            "-b:a", "32k",
            "-c:a", "libopus",
            output_path
        ]

        # non-blocking subprocess execution
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # wait with timeout
        try:
            await asyncio.wait_for(process.communicate(), timeout=60)
        except asyncio.TimeoutError:
            process.kill()
            await status_msg.edit_text(TEXTS["convert_to_voice"]["timeout"])
            return

        if process.returncode != 0:
            await status_msg.edit_text(TEXTS["convert_to_voice"]["failed"])
            return

        # Send Voice
        with open(output_path, "rb") as voice:
            await update.message.reply_voice(
                voice=voice, 
                reply_to_message_id=update.message.reply_to_message.message_id
            )
        
        # cleanup status message
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(TEXTS["convert_to_voice"]["failed"])
    finally:
        # File Cleanup
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)

async def convert_to_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    # must be a reply
    if not message.reply_to_message:
        await message.reply_text(TEXTS["convert_to_voice"]["help"], parse_mode="HTML")
        return

    replied = message.reply_to_message
    
    # initialize variables
    file_obj = None
    input_ext = ""
    duration = 0
    file_size = 0

    # detect media type
    if replied.audio:
        file_obj = await replied.audio.get_file()
        duration = replied.audio.duration
        file_size = replied.audio.file_size
        input_ext = ".mp3"
    elif replied.voice:
        file_obj = await replied.voice.get_file()
        duration = replied.voice.duration
        file_size = replied.voice.file_size
        input_ext = ".ogg"
    elif replied.video:
        file_obj = await replied.video.get_file()
        duration = replied.video.duration
        file_size = replied.video.file_size
        input_ext = ".mp4"
    elif replied.video_note:
        file_obj = await replied.video_note.get_file()
        duration = replied.video_note.duration
        file_size = replied.video_note.file_size
        input_ext = ".mp4"
    elif replied.document:
        mime = replied.document.mime_type or ""
        if mime.startswith("audio/") or mime.startswith("video/"):
            file_obj = await replied.document.get_file()
            file_size = replied.document.file_size
            input_ext = os.path.splitext(replied.document.file_name or "")[1] or ".bin"
            duration = 0
        else:
            await message.reply_text(TEXTS["convert_to_voice"]["error_not_valid"], parse_mode="HTML")
            return
    else:
        await message.reply_text(TEXTS["convert_to_voice"]["error_not_valid"], parse_mode="HTML")
        return

    # validate constraints
    if duration and duration > MAX_DURATION:
        await message.reply_text(TEXTS["convert_to_voice"]["error_duration"], parse_mode="HTML")
        return

    if file_size > MAX_FILE_SIZE:
        await message.reply_text(TEXTS["convert_to_voice"]["error_size"], parse_mode="HTML")
        return

    # add to queue
    queue_len = conversion_queue.qsize()
    position = queue_len + 1
    
    status_msg = await message.reply_text(TEXTS["convert_to_voice"]["added_to_queue"].format(position=position))
    
    # store for status updates
    waiting_users.append({'chat_id': message.chat_id, 'message_id': status_msg.message_id})
    
    # push to queue
    await conversion_queue.put((update, context, file_obj, input_ext, status_msg))
