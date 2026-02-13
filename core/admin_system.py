from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from io import BytesIO
import json
from asyncping3 import ping

from core.config_loader import DBH, TEXTS, reload_config, reload_texts
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
    (total_users, banned_users, today_users, total_usage,
        today_usage, total_memes, unverified_memes, today_memes
    ) = await DBH.bot_status()

    return TEXTS["admin"]["panel_text"].format(
        jdatetime=get_persian_datetime_text(),
        today_user_count=to_persian_digits(today_users),
        today_usage_count=to_persian_digits(today_usage),
        new_meme_count=to_persian_digits(today_memes),
        total_user_count=to_persian_digits(total_users),
        total_usage_count=to_persian_digits(total_usage),
        banned_user_count=to_persian_digits(banned_users),
        total_meme_count=to_persian_digits(total_memes),
        unverified_meme_count=to_persian_digits(unverified_memes),
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
    target = None
    if context.args:
        key = context.args[0]
        user = await DBH.get_user(key)
        if not user:
            await update.effective_chat.send_message(TEXTS["errors"]["user_notfound"], parse_mode="HTML")
            return
        target_user = key

    # Get all target chat IDs
    chat_ids = []
    if target_user:
        chat_ids = [target_user]
    else:
        with DBH._connect() as con:
            cur = con.cursor()
            # Add all active user IDs
            user_ids = [row[0] for row in cur.execute("SELECT user_id FROM users").fetchall()]
        
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

### --- Admin view user information Command --- ###
async def admin_userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
    if not await check_user(update, context, check_force_join=False):
        return

    # check is admin or owner
    if not await is_admin(update.effective_user.id):
        return

    query = update.callback_query
    is_edit = query is not None

    row = None
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

        row = await DBH.get_user(target_user_id)
        if not row:
            await update.effective_chat.send_message(
                TEXTS["errors"]["user_notfound"],
                parse_mode="HTML"
            )
            return

    # called from callback button
    elif is_edit and user_id:
        target_user_id = user_id
        row = await DBH.get_user(target_user_id)

        if not row:
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
    banned = row["banned"]

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "✅ رفع بن" if banned else "🚫 بن",
            callback_data=f"admin_banuser:{target_user_id}"
        )]
    ])

    try:
        chat = await context.bot.get_chat(target_user_id)
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
    user_data = await DBH.get_user(user_id) or (None, None)
    banned, created_at = user_data
    user_status = await DBH.user_status(user_id) or (None, None, None, None, None)
    now = now_ts()
    text = TEXTS["admin"]["user_info"].format(
        user_id=user_id,
        total_memes=to_persian_digits(user_status["total_memes"]) if user_status["total_memes"] is not None else "-",
        unverified_memes=to_persian_digits(user_status["unverified_memes"]) if user_status["unverified_memes"] is not None else "-",
        today_memes=to_persian_digits(user_status["today_memes"]) if user_status["today_memes"] is not None else "-",
        total_usage=to_persian_digits(user_status["total_usage"]) if user_status["total_usage"] is not None else "-",
        today_usage=to_persian_digits(user_status["today_usage"]) if user_status["today_usage"] is not None else "-",
        created_at=to_persian_digits(fmt_ts(created_at)) if created_at else "-",
        created_ago=to_persian_digits(human_ago(max(0, now - (created_at or now)))) if created_at else "-",
        status="🚫 بن شده" if banned else "✅ عادی"
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
    
    elif data.startswith("admin_banuser:"):
        target_user_id = int(data.split(":")[1])
        user = await DBH.get_user(target_user_id)

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
        
        DBH.set_ban(target_user_id, not user["banned"])
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
        
        try:
            await query.answer(TEXTS["admin"]["remove_all_unverified"]["pending"], show_alert=False)
        except Exception:
            pass

        removed = 0
        failed = 0
        # fetch unverified memes and their review message info
        with DBH._connect_sync() as con:
            cur = con.cursor()
            rows = cur.execute("SELECT uuid, review_chat_id, review_message_id FROM memes WHERE is_verified = 0 AND is_banned = 0").fetchall()

        for row in rows:
            uuid = row[0]
            review_chat_id = row[1]
            review_message_id = row[2]
            try:
                # try to remove review message if available
                if review_chat_id and review_message_id:
                    try:
                        await context.bot.delete_message(chat_id=review_chat_id, message_id=review_message_id)
                    except Exception:
                        pass

                # remove all meme related records
                DBH.delete_meme(uuid)
                removed += 1
            except Exception:
                failed += 1

        # update admin panel and notify result
        try:
            await query.edit_message_text(await admin_panel_text(), reply_markup=admin_panel_keyboard(update.effective_user.id), parse_mode="HTML")
        except Exception:
            pass

        try:
            await query.answer(TEXTS["admin"]["remove_all_unverified"]["result"].format(removed=removed, failed=failed), show_alert=True)
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
        unbanned = await DBH.unban_all_users()
        await query.answer(TEXTS["admin"]["unban_all"].format(count=to_persian_digits(unbanned)), show_alert=True)
        if unbanned > 0:
            await query.edit_message_text(await admin_panel_text(), reply_markup=admin_panel_keyboard(update.effective_user.id), parse_mode="HTML")
    
    elif data == "admin_panel":
        await query.edit_message_text(await admin_panel_text(), reply_markup=admin_panel_keyboard(update.effective_user.id), parse_mode="HTML")
        return