from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import aiosqlite

from container import meme_service
from core.config_loader import TEXTS
from core.utils import is_admin, is_content_manager, check_user, fmt_ts

### --- Get Meme --- ###
async def get_meme(update: Update, context: ContextTypes.DEFAULT_TYPE, uuid: str | None = None):
    if not await check_user(update, context):
        return

    user = update.effective_user
    message = update.effective_message
    query = update.callback_query

    # permission check
    if not await is_content_manager(user.id):
        return

    # resolve meme uuid
    if not uuid:
        if not message or not message.reply_to_message:
            await message.reply_text(TEXTS["errors"]["reply_only"])
            return

        replied = message.reply_to_message
        file_id = None

        if replied.video:
            file_id = replied.video.file_id
        elif replied.voice:
            file_id = replied.voice.file_id

        if not file_id:
            await message.reply_text(TEXTS["meme"]["meme_admin"]["errors"]["file_id"])
            return

        meme = await meme_service.get_meme_by_file_id(file_id)
        if not meme:
            await message.reply_text(TEXTS["meme"]["meme_admin"]["errors"]["meme_not_found"])
            return

        uuid = meme.uuid

    # load meme info
    meme = await meme_service.get_meme_full_details(uuid)
    if not meme:
        await message.reply_text(TEXTS["meme"]["meme_admin"]["errors"]["meme_not_found"])
        return

    # keyboard
    keyboard = [
        [
            InlineKeyboardButton(TEXTS["meme"]["meme_admin"]["buttons"]["remove"], callback_data=f"admin_delete_meme:{uuid}", api_kwargs={"style": "danger"}),
            InlineKeyboardButton(TEXTS["meme"]["meme_admin"]["buttons"]["ban_change"], callback_data=f"admin_ban_meme:{uuid}", api_kwargs={"style": "primary"}),
        ],
    ]
    if not meme.is_verified:
        keyboard.append([
            InlineKeyboardButton(TEXTS["meme"]["meme_admin"]["buttons"]["verify"], callback_data=f"admin_toggle_verify:{uuid}", api_kwargs={"style": "success"})
        ])

    # info text
    info_text = TEXTS["meme"]["meme_admin"]["info"].format(
        uuid=meme.uuid,
        title=meme.title or "بدون عنوان",
        tags=", ".join(meme.tags) if meme.tags else "بدون تگ",
        file_id=meme.file_id,
        type=meme.type,
        publisher_id=meme.publisher_user_id,
        is_verified="بله ✅" if meme.is_verified else "خیر ❌",
        is_banned="بله 🚫" if meme.is_banned else "خیر ✅",
        created_at=fmt_ts(meme.created_at)
    )

    # send edit message
    if query:
        await query.edit_message_text(info_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await message.reply_text(info_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def edit_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user(update, context):
        return

    user = update.effective_user
    message = update.effective_message

    if not await is_content_manager(user.id):
        await message.reply_text(TEXTS["errors"]["access_denied"])
        return

    if not message.reply_to_message:
        await message.reply_text(TEXTS["errors"]["reply_only"])
        return

    replied = message.reply_to_message
    file_id = None

    if replied.video:
        file_id = replied.video.file_id
    elif replied.voice:
        file_id = replied.voice.file_id

    if not file_id:
        await message.reply_text(TEXTS["meme"]["meme_admin"]["errors"]["file_id"])
        return

    meme = await meme_service.get_meme_by_file_id(file_id)
    if not meme:
        await message.reply_text(TEXTS["meme"]["meme_admin"]["errors"]["meme_not_found"])
        return

    new_title = message.text.partition(" ")[2].strip()

    if not new_title:
        await message.reply_text(TEXTS["meme"]["meme_admin"]["edit_title"]["enter_title"])
        return

    if len(new_title) < 3 or len(new_title) > 100:
        await message.reply_text(TEXTS["meme"]["errors"]["error_title_length"])
        return

    await meme_service.update_title(meme.uuid, new_title)

    if meme.review_chat_id and meme.review_message_id:
        chat_info = await context.bot.get_chat(meme.publisher_user_id)
        publisher_fullname = chat_info.full_name
        caption_text = TEXTS["meme"]["content_manager_caption"].format(
            title=new_title, tags=", ".join(meme.tags), publisher=f"{publisher_fullname} ({meme.publisher_user_id})"
        )
        try:
            await context.bot.edit_message_caption(chat_id=meme.review_chat_id, message_id=meme.review_message_id, caption=caption_text)
        except Exception:
            pass

    await message.reply_text(TEXTS["meme"]["meme_admin"]["edit_title"]["success"].format(new_title=new_title), parse_mode="HTML")


async def edit_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user(update, context):
        return

    user = update.effective_user
    message = update.effective_message

    if not await is_content_manager(user.id):
        await message.reply_text(TEXTS["errors"]["access_denied"])
        return

    if not message.reply_to_message:
        await message.reply_text(TEXTS["errors"]["reply_only"])
        return

    replied = message.reply_to_message
    file_id = None

    if replied.video:
        file_id = replied.video.file_id
    elif replied.voice:
        file_id = replied.voice.file_id

    if not file_id:
        await message.reply_text(TEXTS["meme"]["meme_admin"]["errors"]["file_id"])
        return

    meme = await meme_service.get_meme_by_file_id(file_id)
    if not meme:
        await message.reply_text(TEXTS["meme"]["meme_admin"]["errors"]["meme_not_found"])
        return

    new_tags = message.text.split(maxsplit=1)
    if len(new_tags) < 2:
        await message.reply_text(TEXTS["meme"]["meme_admin"]["edit_tags"]["enter_tags"], parse_mode="HTML")
        return

    args = new_tags[1].strip()

    tags = [tag.strip() for tag in args.split("\n") if tag.strip()]

    if not 3 <= len(tags) <= 8:
        await message.reply_text(TEXTS["meme"]["errors"]["error_invalid_tag_count"])
        return

    for tag in tags:
        if len(tag) > 30:
            await message.reply_text(TEXTS["meme"]["errors"]["error_tag_too_long"].format(tag=tag))
            return
        
    await meme_service.update_tags(meme.uuid, tags)

    if meme.review_chat_id and meme.review_message_id:
        chat_info = await context.bot.get_chat(meme.publisher_user_id)
        publisher_fullname = chat_info.full_name
        caption_text = TEXTS["meme"]["content_manager_caption"].format(
            title=meme.title, tags=', '.join(tags), publisher=f"{publisher_fullname} ({meme.publisher_user_id})"
        )
        try:
            await context.bot.edit_message_caption(chat_id=meme.review_chat_id, message_id=meme.review_message_id, caption=caption_text)
        except Exception:
            pass

    await message.reply_text(TEXTS["meme"]["meme_admin"]["edit_tags"]["success"].format(new_tags=", ".join(tags)), parse_mode="HTML")

async def meme_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user(update, context, check_force_join=False):
        return
    
    query = update.callback_query
    data = query.data or ""
    user_id = update.effective_user.id

    if not await is_content_manager(user_id):
        await query.answer(TEXTS["errors"]["access_denied"], show_alert=True)
        return

    if data.startswith("admin_delete_meme:"):
        uuid = data.split(":")[1]
        if not await is_admin(user_id):
            await query.answer(TEXTS["errors"]["access_denied"], show_alert=True)
            return
        meme = await meme_service.get_meme_full_details(uuid)
        if meme.review_chat_id and meme.review_message_id:
            try:
                await context.bot.delete_message(chat_id=meme.review_chat_id, message_id=meme.review_message_id)
            except:
                pass

        if await meme_service.delete_meme(uuid):
            await query.answer(TEXTS["meme"]["meme_admin"]["alert"]["remove_success"], show_alert=True)
        else:
            await query.answer(TEXTS["meme"]["meme_admin"]["alert"]["remove_failed"], show_alert=True)
      
        try:
            await context.bot.delete_message(update.effective_chat.id, query.message.message_id)
        except:
            pass

    elif data.startswith("admin_ban_meme:"):
        uuid = data.split(":")[1]
        if not await is_content_manager(user_id):
            await query.answer(TEXTS["errors"]["access_denied"], show_alert=True)
            return
        
        meme = await meme_service.get_meme_full_details(uuid)
        if not meme:
            await query.answer(TEXTS["errors"]["not_found"], show_alert=True)
            return
        
        await meme_service.set_ban(uuid, not meme.is_banned)
        if not meme.is_banned:
            if meme.review_chat_id and meme.review_message_id:
                try:
                    await context.bot.delete_message(chat_id=meme.review_chat_id, message_id=meme.review_message_id)
                except:
                    pass

        await query.answer(TEXTS["meme"]["meme_admin"]["alert"]["ban_success"], show_alert=True)

        try:
            await get_meme(update, context, uuid)
        except:
            pass

    elif data.startswith("admin_toggle_verify:"):
        uuid = data.split(":")[1]

        meme = await meme_service.get_meme_full_details(uuid)
        if not meme:
            await query.answer(TEXTS["errors"]["not_found"], show_alert=True)
            return

        if meme.is_verified:
            await query.answer(TEXTS["meme"]["meme_admin"]["alert"]["already_verified"], show_alert=True)
            return

        await meme_service.verify_meme(uuid, True)
        await query.answer(TEXTS["meme"]["meme_admin"]["alert"]["verify_success"], show_alert=True)

        try:
            await get_meme(update, context, uuid)
        except Exception:
            pass