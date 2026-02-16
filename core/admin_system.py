from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from io import BytesIO
import json
from asyncping3 import ping

from container import user_service, meme_service, status_service
from core.config_loader import TEXTS, reload_config, reload_texts
from core.utils import check_user, is_admin, is_owner, now_ts, fmt_ts, human_ago, to_persian_digits, get_persian_datetime_text


### --- Admin Panel --- ###
def admin_panel_keyboard(user_id: int):
    rows = [
        [
            InlineKeyboardButton(TEXTS["admin"]["panel_keyboard"]["ping_bot"], callback_data="admin_ping", api_kwargs={"style": "success"})
        ]
    ]
    if is_owner(user_id):
        rows.extend([
            [
                InlineKeyboardButton(TEXTS["admin"]["panel_keyboard"]["remove_all_unverified"], callback_data="admin_remove_unverified", api_kwargs={"style": "danger"})
            ],
            [
                InlineKeyboardButton(TEXTS["admin"]["panel_keyboard"]["unban_all"], callback_data="admin_unban_all", api_kwargs={"style": "danger"})
            ],
            [
                InlineKeyboardButton(TEXTS["admin"]["panel_keyboard"]["reload_config"], callback_data="reload_config", api_kwargs={"style": "primary"})
            ],
            [
                InlineKeyboardButton(TEXTS["admin"]["panel_keyboard"]["reload_texts"], callback_data="reload_texts", api_kwargs={"style": "primary"})
            ]
        ])
    return InlineKeyboardMarkup(rows)

async def admin_panel_text():
    status = await status_service.get_dashboard_stats()

    return TEXTS["admin"]["panel_text"].format(
        jdatetime=get_persian_datetime_text(),
        today_user_count=to_persian_digits(status.today_users),
        today_usage_count=to_persian_digits(status.today_usage),
        new_meme_count=to_persian_digits(status.today_memes),
        total_user_count=to_persian_digits(status.total_users),
        total_usage_count=to_persian_digits(status.total_usage),
        banned_user_count=to_persian_digits(status.banned_users),
        total_meme_count=to_persian_digits(status.total_memes),
        unverified_meme_count=to_persian_digits(status.unverified_memes),
    )

async def adminpanel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ["group", "supergroup", "channel"]:
        return
    if not await check_user(update, context, check_force_join=False):
        return
    if not await is_admin(update.effective_user.id):
        return
    await update.effective_chat.send_message(await admin_panel_text(), reply_markup=admin_panel_keyboard(update.effective_user.id), parse_mode="HTML")

### --- Broadcast Command --- ###
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user(update, context, check_force_join=False):
        return

    # Check is owner
    if not is_owner(update.effective_user.id):
        return
    
    # If not a reply, show usage help
    if not update.message or not update.message.reply_to_message:
        await update.effective_chat.send_message(TEXTS["admin"]["broadcast"]["message"], parse_mode="HTML")
        return
    
    # Check if broadcasting to all or single user
    user_id = None
    if context.args:
        user_id = context.args[0]
        user = await user_service.get_user(user_id)
        if not user:
            await update.effective_chat.send_message(TEXTS["errors"]["user_notfound"], parse_mode="HTML")
            return
        target_user = user_id

    # Get all target chat IDs
    chat_ids = []
    if target_user:
        chat_ids = [target_user]
    else:
        user_ids = await user_service.get_all_user_ids()
        
        # Merge lists and remove duplicates
        chat_ids = list(set(user_ids))
    
    # Forward message
    message = update.message.reply_to_message
    success = 0
    failed = 0
    for chat_id in chat_ids:
        try:
            await context.bot.copy_message(chat_id=chat_id, from_chat_id=message.chat_id, message_id=message.message_id)
            success += 1
        except Exception:
            failed += 1
    
    await update.effective_chat.send_message(TEXTS["admin"]["broadcast"]["result"].format(success=success, failed=failed), parse_mode="HTML")

### --- Admin view list of all users Command --- ###
async def show_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    if not is_owner(update.effective_user.id):
        return
    
    PAGE_SIZE = 20

    total = await user_service.get_user_count()
    if total == 0:
        if update.callback_query:
            await update.callback_query.edit_message_text(TEXTS["errors"]["user_notfound"])
        else:
            await update.message.reply_text(TEXTS["errors"]["user_notfound"])
        return

    max_page = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, max_page))
    offset = (page - 1) * PAGE_SIZE

    users = await user_service.get_users_page(PAGE_SIZE, offset)

    message = (TEXTS["admin"]["users_list"]["header"].format(
        total=to_persian_digits(total), page=to_persian_digits(page), max_page=to_persian_digits(max_page))
    ) + "\n".join([f"‎🔹<code>{user.user_id}</code> - {user.full_name or 'بدون نام'}" for user in users])

    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"admin_show_users:{page-1}"))
    if page < max_page:
        buttons.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"admin_show_users:{page+1}"))

    markup = InlineKeyboardMarkup([buttons]) if buttons else None

    if update.callback_query:
        await update.callback_query.edit_message_text(message[:4096], reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(message[:4096], reply_markup=markup, parse_mode="HTML")

### --- Admin view user information Command --- ###
async def admin_userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
    if not await check_user(update, context, check_force_join=False):
        return

    # check is admin or owner
    if not await is_admin(update.effective_user.id):
        return

    query = update.callback_query
    is_edit = query is not None

    user = None
    target_user_id = None

    # called from command with args
    if context.args:
        try:
            target_user_id = int(context.args[0])
        except ValueError:
            await update.effective_chat.send_message(
                TEXTS["errors"]["invalid_command"],
                parse_mode="HTML"
            )
            return

        user = await user_service.get_user(target_user_id)
        if not user:
            await update.effective_chat.send_message(
                TEXTS["errors"]["user_notfound"],
                parse_mode="HTML"
            )
            return

    # called from callback button
    elif is_edit and user_id:
        target_user_id = user_id
        user = await user_service.get_user(target_user_id)

        if not user:
            await query.answer(TEXTS["errors"]["user_notfound"])
            return

    # invalid usage
    else:
        await update.effective_chat.send_message(
            f'<b>{TEXTS["errors"]["invalid_command"]}</b>',
            parse_mode="HTML"
        )
        return

    # build output
    
    text = await generate_userinfo_text(target_user_id)
    banned = user.banned

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "✅ رفع بن" if banned else "🚫 بن",
            callback_data=f"admin_banuser:{target_user_id}"
        )]
    ])

    try:
        chat = await context.bot.get_chat(target_user_id)
        await user_service.register_user(target_user_id, chat.full_name) # update full name
        full_info = chat.to_dict()
    except Exception:
        full_info = "-"

    # send or edit message

    if is_edit:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await update.effective_chat.send_message(text, reply_markup=keyboard, parse_mode="HTML")
        try:
            data = BytesIO(json.dumps(full_info, indent=4, ensure_ascii=False).encode())
            data.name = f"user_{target_user_id}.json"
            await update.effective_chat.send_document(data)
        except Exception as e:
            await update.effective_chat.send_message(TEXTS["errors"]["failed_to_fetch_user"])

# Generate userinfo text from user_id
async def generate_userinfo_text(user_id: int) -> str:
    user = await user_service.get_user(user_id)
    user_status = await status_service.get_user_stats(user_id)
    now = now_ts()
    text = TEXTS["admin"]["user_info"].format(
        user_id=user_id,
        total_memes=to_persian_digits(user_status.total_memes) if user_status.total_memes is not None else "-",
        unverified_memes=to_persian_digits(user_status.unverified_memes) if user_status.unverified_memes is not None else "-",
        today_memes=to_persian_digits(user_status.today_memes) if user_status.today_memes is not None else "-",
        total_usage=to_persian_digits(user_status.total_usage) if user_status.total_usage is not None else "-",
        today_usage=to_persian_digits(user_status.today_usage) if user_status.today_usage is not None else "-",
        created_at=to_persian_digits(fmt_ts(user.created_at)) if user.created_at else "-",
        created_ago=to_persian_digits(human_ago(max(0, now - (user.created_at or now)))) if user.created_at else "-",
        status="🚫 بن شده" if user.banned else "✅ عادی"
    )
    return text

### --- Admin Callbacks --- ###
async def admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user(update, context, check_force_join=False):
        return
    
    query = update.callback_query
    data = query.data or ""
    user_id = update.effective_user.id

    if not await is_admin(user_id):
        await query.answer(TEXTS["errors"]["access_denied"], show_alert=True)
        return
    
    elif data.startswith("admin_show_users:"):
        page = int(data.split(":")[1])
        await show_all_users(update, context, page=page)
        return
    
    elif data.startswith("admin_banuser:"):
        target_user_id = int(data.split(":")[1])
        user = await user_service.get_user(target_user_id)

        # Check ban yourself
        if user_id == target_user_id:
            await query.answer("میخوای خودتو بن کنی 😔", show_alert=True)
            return
        
        # Check owner
        if is_owner(target_user_id):
            await query.answer(TEXTS["errors"]["access_denied"], show_alert=True)
            return

        # Check is user available
        if not user:
            await query.answer(TEXTS["errors"]["user_notfound"], show_alert=True)
            return
        
        user_service.set_ban(target_user_id, not user.banned)
        await query.answer(TEXTS["admin"]["ban_state_changed"], show_alert=True)
        await admin_userinfo(update, context, target_user_id)
        return
    
    elif data == "reload_config":
        if not is_owner(user_id):
            await query.answer(TEXTS["errors"]["access_denied"], show_alert=True)
            return

        if reload_config():
            await query.answer(TEXTS["admin"]["reload_config"]["success"])
        else:
            await query.answer(TEXTS["admin"]["reload_config"]["error"])
        return
    
    elif data == "reload_texts":
        if not is_owner(user_id):
            await query.answer(TEXTS["errors"]["access_denied"], show_alert=True)
            return

        if reload_texts():
            await query.answer(TEXTS["admin"]["reload_texts"]["success"])
        else:
            await query.answer(TEXTS["admin"]["reload_texts"]["error"])
        return
    
    elif data == "admin_remove_unverified":
        if not is_owner(user_id):
            await query.answer(TEXTS["errors"]["access_denied"], show_alert=True)
            return

        removed = 0
        failed = 0
        # fetch unverified memes and their review message info
        memes = await meme_service.get_all_unverified()

        for meme in memes:
            try:
                # try to remove review message if available
                if meme.review_chat_id and meme.review_message_id:
                    try:
                        await context.bot.delete_message(chat_id=meme.review_chat_id, message_id=meme.review_message_id)
                    except Exception:
                        pass

                # remove all meme related records
                await meme_service.delete_meme(meme.uuid)
                removed += 1
            except Exception:
                failed += 1

        # show result
        try:
            await query.answer(TEXTS["admin"]["remove_all_unverified"].format(removed=removed, failed=failed), show_alert=True)
        except Exception as e:
            print(e)
            pass

        # update admin panel and notify result
        if removed > 0:
            try:
                await query.edit_message_text(await admin_panel_text(), reply_markup=admin_panel_keyboard(update.effective_user.id), parse_mode="HTML")
            except Exception:
                pass

        return

    elif data == "admin_ping":
        result = await ping("149.154.166.110")
        if result is not None:
            await query.answer(TEXTS["admin"]["ping_result"].format(ping=to_persian_digits(f"{result*1000:.2f}")), show_alert=True)

    elif data == "admin_unban_all":
        if not is_owner(user_id):
            await query.answer(TEXTS["errors"]["access_denied"], show_alert=True)
            return
        unbanned = await user_service.unban_all_users()
        await query.answer(TEXTS["admin"]["unban_all"].format(count=to_persian_digits(unbanned)), show_alert=True)
        if unbanned > 0:
            await query.edit_message_text(await admin_panel_text(), reply_markup=admin_panel_keyboard(update.effective_user.id), parse_mode="HTML")
    
    elif data == "admin_panel":
        await query.edit_message_text(await admin_panel_text(), reply_markup=admin_panel_keyboard(update.effective_user.id), parse_mode="HTML")
        return