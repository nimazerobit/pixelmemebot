from telegram import (Update, InlineQueryResultsButton, InlineQueryResultCachedVideo, 
    InlineQueryResultCachedVoice, InlineKeyboardMarkup, InlineKeyboardButton)
from telegram.ext import ContextTypes, ConversationHandler
from uuid import uuid4

from container import meme_service
from core.config_loader import TEXTS, CFG
from core.utils import has_active_private_chat, is_admin, is_content_manager, check_user

PAGE_SIZE = 50

async def inline_meme_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inline_query = update.inline_query
    raw_query = inline_query.query.strip()
    user_id = inline_query.from_user.id

    # parse search query & caption
    search_query = ""
    caption = None

    if "@" in raw_query:
        parts = raw_query.split("@", 1)
        search_query = parts[0].strip()
        caption = parts[1].strip() or None
    else:
        search_query = raw_query

    # telegram caption limit safety
    if caption:
        caption = caption[:1024]

    # parse offset
    try:
        offset = int(inline_query.offset) if inline_query.offset else 0
    except ValueError:
        offset = 0

    # auth check
    pv_active = await has_active_private_chat(context.bot, user_id)

    if not pv_active:
        await context.bot.answer_inline_query(
            inline_query.id,
            results=[],
            cache_time=5,
            is_personal=True,
            button=InlineQueryResultsButton(
                text="🤖 برای استفاده از ربات کلیک کنید",
                start_parameter="inline"
            )
        )
        return

    # fetch memes
    fetch_limit = PAGE_SIZE + 1

    memes = await meme_service.search_memes_for_inline(
        user_id=user_id,
        query=search_query,
        offset=offset,
        limit=fetch_limit
    )

    if not memes:
        await context.bot.answer_inline_query(
            inline_query.id,
            results=[],
            cache_time=1,
            is_personal=True,
            next_offset="",
            button=InlineQueryResultsButton(
                text="نتیجه ای پیدا نشد",
                start_parameter="inline"
            )
        )
        return

    # pagination
    if len(memes) > PAGE_SIZE:
        next_offset = str(offset + PAGE_SIZE)
        memes = memes[:PAGE_SIZE]
    else:
        next_offset = ""

    # build inline results
    results = []

    for meme in memes:
        meme_uuid = meme["uuid"]
        
        tags = meme.get("tags", "") 
        result_id = str(meme_uuid)

        description = caption if caption else tags

        if meme["type"] == "video":
            results.append(
                InlineQueryResultCachedVideo(
                    id=result_id,
                    video_file_id=meme["file_id"],
                    title=meme["title"],
                    description=description,
                    caption=caption
                )
            )

        elif meme["type"] == "voice":
            results.append(
                InlineQueryResultCachedVoice(
                    id=result_id,
                    voice_file_id=meme["file_id"],
                    title=meme["title"],
                    caption=caption
                )
            )

    # answer inline query
    await context.bot.answer_inline_query(
        inline_query.id,
        results=results,
        cache_time=0,
        is_personal=True,
        next_offset=next_offset
    )

async def on_meme_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chosen_inline_result
    user_id = result.from_user.id
    meme_uuid = result.result_id
    query_text = result.query
    await meme_service.record_usage(meme_uuid, user_id, query_text)


### --- Add New MEME --- ###
MEDIA, TITLE, TAGS = range(3)
async def new_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ["group", "supergroup", "channel"]:
        await update.message.reply_text(TEXTS["errors"]["private_message_only"])
        return
    if not await check_user(update, context):
        return
    context.user_data.clear()
    await update.effective_chat.send_message(TEXTS["cancel_note"])
    await update.message.reply_text(TEXTS["meme"]["ask_media"])
    return MEDIA

async def get_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    file_id = None
    media_type = None
    # duration = None

    if message.video:
        file_id = message.video.file_id
        media_type = "video"
        # duration = message.video.duration

    elif message.voice:
        file_id = message.voice.file_id
        media_type = "voice"
        # duration = message.voice.duration

    elif message.audio:
        await message.reply_text(TEXTS["meme"]["errors"]["convert_to_voice"])
        return ConversationHandler.END

    else:
        await message.reply_text(TEXTS["meme"]["errors"]["error_invalid_media"])
        return ConversationHandler.END
    
    # duplicate file_id check
    if not await is_content_manager(message.from_user.id):
        if await meme_service.meme_file_exists(file_id):
            await message.reply_text(TEXTS["meme"]["errors"]["error_duplicate_media"])
            return ConversationHandler.END

    context.user_data["file_id"] = file_id
    context.user_data["media_type"] = media_type

    await update.effective_chat.send_message(TEXTS["meme"]["ask_title"])
    return TITLE

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()

    if len(title) < 3 and len(title) > 100:
        await update.message.reply_text(TEXTS["meme"]["errors"]["error_title_length"])
        return TITLE

    context.user_data["title"] = title
    await update.effective_chat.send_message(TEXTS["meme"]["ask_tags"])
    return TAGS

async def get_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tags = [t.strip() for t in update.message.text.split("\n") if t.strip()]

    if not 3 <= len(tags) <= 8:
        await update.message.reply_text(TEXTS["meme"]["errors"]["error_invalid_tag_count"])
        return TAGS

    for tag in tags:
        if len(tag) > 30:
            await update.message.reply_text(TEXTS["meme"]["errors"]["error_tag_too_long"].format(tag=tag))
            return TAGS

    context.user_data["tags"] = tags
    context.user_data["uuid"] = str(uuid4())

    markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ تایید", callback_data="meme_confirm", api_kwargs={"style": "success"}),
            InlineKeyboardButton("❌ لغو", callback_data="meme_cancel", api_kwargs={"style": "danger"}),
    ]])

    await update.effective_chat.send_message(
        TEXTS["meme"]["ask_confirm"].format(title=context.user_data["title"], tags = ", ".join(tags), type=context.user_data["media_type"]),
        reply_markup=markup,
        parse_mode="HTML"
    )

    return ConversationHandler.END

async def meme_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "meme_cancel":
        context.user_data.clear()
        await query.edit_message_text(TEXTS["meme"]["meme_canceled"])
        return

    data = context.user_data
    publisher_fullname = query.from_user.full_name
    publisher_id = query.from_user.id

    # admin -> instant approve
    if await is_admin(publisher_id):
        await meme_service.add_meme(
            uuid=data["uuid"],
            title=data["title"],
            file_id=data["file_id"],
            type_=data["media_type"],
            publisher_id=publisher_id,
            tags=data["tags"]
        )
        await meme_service.verify_meme(data["uuid"], True)

        await query.edit_message_text(TEXTS["meme"]["meme_added_to_bot"])
        context.user_data.clear()
        return

    # content manager -> send directly to vote channel
    if await is_content_manager(publisher_id):
        await send_to_vote_channel(update, context, data)
        return

    # normal user -> send to content manager group for pre-approval
    await send_to_admin_vote_group(update, context, data)

async def admin_meme_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if not await is_content_manager(user_id):
        await query.answer(TEXTS["errors"]["access_denied"], show_alert=True)
        return

    _, action, uuid = query.data.split(":")
    
    meme = await meme_service.get_meme_full_details(uuid)
    
    if not meme:
        await query.answer(TEXTS["errors"]["not_found"], show_alert=True)
        return

    if action == "reject":
        meme_service.delete_meme(uuid)

        await query.edit_message_caption(
            caption=TEXTS["meme"]["content_manager_rejected"].format(meme_title=meme.title, admin_name=query.from_user.full_name),
            parse_mode="HTML"
        )
        
        try:
            await context.bot.send_message(meme["publisher_user_id"], TEXTS["meme"]["meme_vote_rejected"])
        except:
            pass

    elif action == "approve":
        await send_to_vote_channel(update, context, {
            "uuid": uuid,
            "title": meme["title"],
            "file_id": meme["file_id"],
            "media_type": meme["type"],
            "publisher_user_id": meme["publisher_user_id"],

        })

        await query.edit_message_caption(
            caption=TEXTS["meme"]["content_manager_approved"].format(meme_title=meme["title"], admin_name=query.from_user.full_name),
            parse_mode="HTML"
        )

# --- Meme Voting Logic ---
async def meme_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user(update, context):
        return

    query = update.callback_query

    try:
        _, uuid, vote = query.data.split(":")
        vote = int(vote)
    except ValueError:
        await query.answer(TEXTS["meme"]["alert"]["vote"]["failed"], show_alert=True)
        return

    user_id = query.from_user.id

    # --- validate vote ---
    (current_stats, prev_vote) = await meme_service.get_vote_info(uuid, user_id)
    meme = meme_service.get_meme_full_details(uuid)

    if not meme:
        await query.answer(TEXTS["errors"]["not_found"], show_alert=True)
        return

    if prev_vote == vote:
        await query.answer(TEXTS["meme"]["alert"]["vote"]["already"], show_alert=True)
        return
    
    if meme.publisher_user_id == user_id:
        await query.answer(TEXTS["meme"]["alert"]["vote"]["self"], show_alert=True)
        return

    # --- store / update vote ---
    await meme_service.vote_for_meme(uuid, user_id, vote)
    await query.answer(TEXTS["meme"]["alert"]["vote"]["saved"], show_alert=True)
    (updated_stats, _) = await meme_service.get_vote_info(uuid, user_id)
    likes, dislikes = updated_stats

    # --- admin override ---
    if await is_admin(user_id):
        if vote == 1:
            await meme_service.verify_meme(uuid, True)
            action = "approved"
        else:
            meme_service.set_ban(uuid, True)
            action = "rejected"

        if meme.review_chat_id and meme.review_message_id:
            try:
                await context.bot.delete_message(meme.review_chat_id, meme.review_message_id)
            except:
                pass

        if meme.publisher_user_id:
            await context.bot.send_message(meme.publisher_user_id, TEXTS["meme"][f"meme_vote_{action}"])
        return

    # --- approval rule ---
    if likes >= CFG["MEME_APPROVE_UPVOTES"]:
        await meme_service.verify_meme(uuid, True)

        if meme.review_chat_id and meme.review_message_id:
            try:
                await context.bot.delete_message(
                    meme.review_chat_id,
                    meme.review_message_id
                )
            except:
                pass

        if meme.publisher_user_id:
            await context.bot.send_message(
                meme.publisher_user_id,
                TEXTS["meme"]["meme_vote_approved"]
            )
        return

    # --- rejection rule ---
    if dislikes >= likes + CFG["MEME_REJECT_GAP"]:
        if meme.review_chat_id and meme.review_message_id:
            try:
                await context.bot.delete_message(
                    meme.review_chat_id,
                    meme.review_message_id
                )
            except:
                pass

        if meme.publisher_user_id:
            await context.bot.send_message(meme.publisher_user_id, TEXTS["meme"]["meme_vote_rejected"])
        meme_service.delete_meme(uuid)
        return

    # --- update buttons with live counts ---
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(TEXTS["meme"]["button"]["upvote"].format(count=likes), callback_data=f"meme_vote:{uuid}:1", api_kwargs={"style": "success"}),
        InlineKeyboardButton(TEXTS["meme"]["button"]["downvote"].format(count=dislikes), callback_data=f"meme_vote:{uuid}:-1", api_kwargs={"style": "danger"}),
    ]])
    try:
        await query.edit_message_reply_markup(reply_markup=keyboard)
    except:
        pass

# helper function to send meme to vote channel
async def send_to_vote_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, user_data):
    query = update.callback_query

    vote_keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(TEXTS["meme"]["button"]["upvote"].format(count="بدون رای"), callback_data=f"meme_vote:{user_data['uuid']}:1", api_kwargs={"style": "success"}),
        InlineKeyboardButton(TEXTS["meme"]["button"]["downvote"].format(count="بدون رای"), callback_data=f"meme_vote:{user_data['uuid']}:-1", api_kwargs={"style": "danger"}),
    ]])

    if "tags" in user_data and user_data["tags"]:
        tags = user_data["tags"]
    else:
        meme = await meme_service.get_meme_full_details(user_data["uuid"])
        tags = meme.tags

    caption = TEXTS["meme"]["vote_caption"].format(
        title=user_data["title"],
        tags=', '.join(tags)
    )

    is_meme_existing = True if await meme_service.get_meme_full_details(user_data["uuid"]) else False

    if not is_meme_existing:
        # save as unverified meme to database
        await meme_service.add_meme(
            uuid=user_data["uuid"],
            title=user_data["title"],
            file_id=user_data["file_id"],
            type_=user_data["media_type"],
            publisher_id=user_data["publisher_user_id"],
            tags=user_data["tags"]
        )

    try:
        message = None
        if user_data["media_type"] == "video":
            message = await context.bot.send_video(
                chat_id=CFG["MEME_REVIEW_CHAT_ID"],
                video=user_data["file_id"],
                caption=caption,
                reply_markup=vote_keyboard,
                parse_mode="HTML"
            )
        elif user_data["media_type"] == "voice":
            message = await context.bot.send_voice(
                chat_id=CFG["MEME_REVIEW_CHAT_ID"],
                voice=user_data["file_id"],
                caption=caption,
                reply_markup=vote_keyboard,
                parse_mode="HTML"
            )
        elif user_data["media_type"] == "audio":
            message = await context.bot.send_audio(
                chat_id=CFG["MEME_REVIEW_CHAT_ID"],
                audio=user_data["file_id"],
                caption=caption,
                reply_markup=vote_keyboard,
                parse_mode="HTML"
            )

        meme_service.set_review_message(user_data["uuid"], message.chat.id, message.message_id)

        context.user_data.clear()
        return

    except Exception:
        await query.edit_message_text(TEXTS["meme"]["errors"]["review_send_failed"])
        return
    
async def send_to_admin_vote_group(update: Update, context: ContextTypes.DEFAULT_TYPE, user_data):
    query = update.callback_query

    admin_keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(TEXTS["meme"]["button"]["approve_admin"], callback_data=f"admin_vote:approve:{user_data['uuid']}", api_kwargs={"style": "success"}),
        InlineKeyboardButton(TEXTS["meme"]["button"]["reject_admin"], callback_data=f"admin_vote:reject:{user_data['uuid']}", api_kwargs={"style": "danger"}),
    ]])

    is_meme_existing = True if await meme_service.get_meme_full_details(user_data["uuid"]) else False
    if not is_meme_existing:
        # save as unverified meme to database
        await meme_service.add_meme(
            uuid=user_data["uuid"],
            title=user_data["title"],
            file_id=user_data["file_id"],
            type_=user_data["media_type"],
            publisher_id=query.from_user.id,
            tags=user_data["tags"]
        )

    try:
        caption_text = TEXTS["meme"]["content_manager_caption"].format(
            title=user_data["title"], tags=', '.join(user_data['tags']), publisher=f"{query.from_user.full_name} ({query.from_user.id})"
        )

        message = None
        if user_data["media_type"] == "video":
            message = await context.bot.send_video(chat_id=CFG["MEME_CONTENT_MANAGER_CHAT_ID"], video=user_data["file_id"], caption=caption_text, reply_markup=admin_keyboard, parse_mode="HTML")
        elif user_data["media_type"] == "voice":
            message = await context.bot.send_voice(chat_id=CFG["MEME_CONTENT_MANAGER_CHAT_ID"], voice=user_data["file_id"], caption=caption_text, reply_markup=admin_keyboard, parse_mode="HTML")
        elif user_data["media_type"] == "audio":
            message = await context.bot.send_audio(chat_id=CFG["MEME_CONTENT_MANAGER_CHAT_ID"], audio=user_data["file_id"], caption=caption_text, reply_markup=admin_keyboard, parse_mode="HTML")

        meme_service.set_review_message(user_data["uuid"], message.chat.id, message.message_id)

        await query.edit_message_text(TEXTS["meme"]["sent_for_review"])
        context.user_data.clear()
        return

    except Exception as e:
        await query.edit_message_text(TEXTS["meme"]["errors"]["review_send_failed"])
        return