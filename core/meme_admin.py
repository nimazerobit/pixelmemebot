from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import aiosqlite

from core.config_loader import DBH, TEXTS
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

        row = await DBH.get_meme_by_file_id(file_id)
        if not row:
            await message.reply_text(TEXTS["meme"]["meme_admin"]["errors"]["meme_not_found"])
            return

        uuid = row["uuid"]

    # load meme info
    meme_info = await DBH.get_meme_info(uuid)
    if not meme_info:
        await message.reply_text(TEXTS["meme"]["meme_admin"]["errors"]["meme_not_found"])
        return

    # keyboard
    keyboard = [
        [
            InlineKeyboardButton(TEXTS["meme"]["meme_admin"]["buttons"]["remove"], callback_data=f"admin_delete_meme:{uuid}", api_kwargs={"style": "danger"}),
            InlineKeyboardButton(TEXTS["meme"]["meme_admin"]["buttons"]["ban_change"], callback_data=f"admin_ban_meme:{uuid}", api_kwargs={"style": "primary"}),
        ],
    ]
    if not meme_info['is_verified']:
        keyboard.append([
            InlineKeyboardButton(TEXTS["meme"]["meme_admin"]["buttons"]["verify"], callback_data=f"admin_toggle_verify:{uuid}", api_kwargs={"style": "success"})
        ])

    # info text
    info_text = TEXTS["meme"]["meme_admin"]["info"].format(
        uuid=meme_info['uuid'],
        title=meme_info['title'] or "بدون عنوان",
        tags=", ".join(meme_info['tags']) if meme_info['tags'] else "بدون تگ",
        file_id=meme_info['file_id'],
        type=meme_info['type'],
        publisher_id=meme_info['publisher_user_id'],
        is_verified="بله ✅" if meme_info['is_verified'] else "خیر ❌",
        is_banned="بله 🚫" if meme_info['is_banned'] else "خیر ✅",
        created_at=fmt_ts(meme_info['created_at'])
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

    row = await DBH.get_meme_by_file_id(file_id)
    if not row:
        await message.reply_text(TEXTS["meme"]["meme_admin"]["errors"]["meme_not_found"])
        return

    uuid = row["uuid"]
    new_title = message.text.partition(" ")[2].strip()

    if not new_title:
        await message.reply_text(TEXTS["meme"]["meme_admin"]["edit_title"]["enter_title"])
        return

    if len(new_title) < 3 or len(new_title) > 100:
        await message.reply_text(TEXTS["meme"]["errors"]["error_title_length"])
        return

    async with aiosqlite.connect(DBH.path) as con:
        await con.execute("UPDATE memes SET title = ? WHERE uuid = ?", (new_title, uuid))
        await con.commit()

    review = DBH.get_review_message(uuid)
    if review and review["review_chat_id"] and review["review_message_id"]:
        publisher_fullname = context.bot.get_chat(row["publisher_user_id"]).full_name
        caption_text = TEXTS["meme"]["content_manager_caption"].format(
            title=new_title, tags=', '.join(row['tags']), publisher=f"{publisher_fullname} ({row['publisher_user_id']})"
        )
        try:
            await context.bot.edit_message_caption(chat_id=review["review_chat_id"], message_id=review["review_message_id"], caption=caption_text)
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

    row = await DBH.get_meme_by_file_id(file_id)
    if not row:
        await message.reply_text(TEXTS["meme"]["meme_admin"]["errors"]["meme_not_found"])
        return

    uuid = row["uuid"]
    new_tags = message.text.split(maxsplit=1)
    if len(new_tags) < 2:
        await message.reply_text(TEXTS["meme"]["meme_admin"]["edit_tags"]["enter_tags"],parse_mode="HTML")
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
        
    async with aiosqlite.connect(DBH.path) as con:
        await con.execute("DELETE FROM meme_tags WHERE meme_uuid = ?", (uuid,))
        await con.executemany("INSERT INTO meme_tags (meme_uuid, tag) VALUES (?, ?)", [(uuid, tag) for tag in tags])
        await con.commit()

    review = DBH.get_review_message(uuid)
    if review and review["review_chat_id"] and review["review_message_id"]:
        publisher_fullname = context.bot.get_chat(row["publisher_user_id"]).full_name
        caption_text = TEXTS["meme"]["content_manager_caption"].format(
            title=row["title"], tags=', '.join(tags), publisher=f"{publisher_fullname} ({row['publisher_user_id']})"
        )
        try:
            await context.bot.edit_message_caption(chat_id=review["review_chat_id"], message_id=review["review_message_id"], caption=caption_text)
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
        review = DBH.get_review_message(uuid)
        if review:
            chat_id, msg_id = review
            try:
                await context.bot.delete_message(chat_id, msg_id)
            except:
                pass

        if await DBH.delete_meme(uuid):
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
        
        row = await DBH.get_meme_info(uuid)
        if not row:
            await query.answer(TEXTS["errors"]["not_found"], show_alert=True)
            return
        
        is_banned = row["is_banned"]
        DBH.set_meme_banned(uuid, not is_banned)
        if not is_banned:
            review = DBH.get_review_message(uuid)
            if review:
                chat_id, msg_id = review
                try:
                    await context.bot.delete_message(chat_id, msg_id)
                except:
                    pass

        await query.answer(TEXTS["meme"]["meme_admin"]["alert"]["ban_success"], show_alert=True)

        try:
            await get_meme(update, context, uuid)
        except:
            pass

    elif data.startswith("admin_toggle_verify:"):
        uuid = data.split(":")[1]

        row = await DBH.get_meme_info(uuid)
        if not row:
            await query.answer(TEXTS["errors"]["not_found"], show_alert=True)
            return

        if row["is_verified"]:
            await query.answer(TEXTS["meme"]["meme_admin"]["alert"]["already_verified"], show_alert=True)
            return

        await DBH.set_meme_verified(uuid, True)
        await query.answer(TEXTS["meme"]["meme_admin"]["alert"]["verify_success"], show_alert=True)

        try:
            await get_meme(update, context, uuid)
        except Exception:
            pass