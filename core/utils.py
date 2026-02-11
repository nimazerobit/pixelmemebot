from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest

import time
import jdatetime
from datetime import datetime
import pytz

from core.config_loader import DBH, CFG, TEXTS

### --- Humanize time --- ###
def human_ago(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} ثانیه"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} دقیقه"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} ساعت"
    days = hours // 24
    if days < 30:
        return f"{days} روز"
    months = days // 30
    if months < 12:
        return f"{months} ماه"
    years = months // 12
    return f"{years} سال"

### --- Return current timestamp --- ###
def now_ts() -> int:
    return int(time.time())

### --- Return current time string --- ###
def fmt_ts(ts: int) -> str:
    dt_tehran = datetime.fromtimestamp(ts, tz=pytz.UTC).astimezone(pytz.timezone("Asia/Tehran"))
    j_dt = jdatetime.datetime.fromgregorian(datetime=dt_tehran)
    return to_persian_digits(
        f"{j_dt.year:04d}-{j_dt.month:02d}-{j_dt.day:02d} "
        f"{j_dt.hour:02d}:{j_dt.minute:02d}:{j_dt.second:02d}"
    )

# persian digit map
PERSIAN_DIGIT_MAP = {
    "0": "۰", "1": "۱", "2": "۲", "3": "۳", "4": "۴",
    "5": "۵", "6": "۶", "7": "۷", "8": "۸", "9": "۹"
}

### --- Return persian digit --- ###
def to_persian_digits(text: str) -> str:
    return "".join(PERSIAN_DIGIT_MAP.get(ch, ch) for ch in str(text))

### --- Return current shamsi datetime --- ###
def get_persian_datetime_text():
    now_tehran = datetime.now(pytz.timezone("Asia/Tehran"))
    j_now = jdatetime.datetime.fromgregorian(datetime=now_tehran)
    weekday_map = {
        0: "شنبه",
        1: "یکشنبه",
        2: "دوشنبه",
        3: "سه‌شنبه",
        4: "چهارشنبه",
        5: "پنجشنبه",
        6: "جمعه",
    }
    weekday = weekday_map[j_now.weekday()]
    date_str = f"{j_now.year}/{j_now.month:02d}/{j_now.day:02d}"
    time_str = now_tehran.strftime("%H:%M")

    return to_persian_digits(f"🗓 امروز {weekday}، تاریخ {date_str}، ساعت {time_str}")

### --- Check is user content manager or not --- ###
async def is_content_manager(user_id: int) -> bool:
    # Check ban status
    row = await DBH.get_user(user_id)
    if row and row["banned"]:
        return False

    # Check role
    return user_id in set(CFG.get("CONTENT_MANAGER", []) + CFG.get("ADMINS", []) + CFG.get("OWNERS", []))

### --- Check is user admin or not --- ###
async def is_admin(user_id: int) -> bool:
    # Check ban status
    row = await DBH.get_user(user_id)
    if row and row["banned"]:
        return False

    # Check role
    return user_id in set(CFG.get("ADMINS", []) + CFG.get("OWNERS", []))

### --- Check is user owner or not --- ###
def is_owner(user_id: int) -> bool:
    # Check role
    return user_id in set(CFG.get("OWNERS", []))

### --- create user --- ###
async def ensure_user(update: Update) -> bool:
    user = update.effective_user
    if user is None:
        return False  # error
    try:
        await DBH.upsert_user(user.id)
        return True
    except Exception:
        return False  # error

### --- Check is user banned or not --- ###
async def ban_guard(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return True
    row = await DBH.get_user(user.id)
    if row and row["banned"]:
        if update.callback_query:
            await update.callback_query.answer(TEXTS["errors"]["banned"])
        else:
            await update.effective_chat.send_message(TEXTS["errors"]["banned"], parse_mode="HTML")
        return True
    return False

### --- Check is user joined channel/group or not --- ###
reported_missing_chats = set()

async def is_user_joined(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Forbidden:
        # Bot cannot access member info (maybe not an admin in channel/group)
        return False
    
async def check_required_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    not_joined_user = []

    for item in CFG["REQUIRED_CHATS"]:
        title = item["title"]
        join_link = item["join_link"]
        chat_id = item["chat_id"]

        try:
            bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
            if bot_member.status in ["left", "kicked"]:
                if chat_id not in reported_missing_chats:
                    for admin_id in CFG["OWNERS"]:
                        await context.bot.send_message(
                            admin_id,
                            text=TEXTS["required_chat"]["bot_not_joined"].format(chat_id=chat_id, title=title)
                        )
                    reported_missing_chats.add(chat_id)
                return True
        except BadRequest:
            if chat_id not in reported_missing_chats:
                for admin_id in CFG["OWNERS"]:
                    await context.bot.send_message(
                        admin_id,
                        text=TEXTS["required_chat"]["bot_no_access"].format(chat_id=chat_id, title=title)
                    )
                reported_missing_chats.add(chat_id)
            return True

        if not await is_user_joined(context.bot, chat_id, user_id):
            not_joined_user.append((title, join_link))

    if not_joined_user:
        buttons = [
            [InlineKeyboardButton(title, url=join_link)]
            for title, join_link in not_joined_user
        ]
        reply_markup = InlineKeyboardMarkup(buttons)

        await update.effective_message.reply_text(
            TEXTS["required_chat"]["message"],
            reply_markup=reply_markup
        )
        return False

    return True

async def check_user(update: Update, context: ContextTypes.DEFAULT_TYPE, check_force_join: bool=True, check_ban: bool=True, check_user_db: bool=True):
    if check_user_db:
        await ensure_user(update)
    if check_ban:
        if await ban_guard(update):
            return False
    if check_force_join or await is_admin(update.effective_user.id):
        if not await check_required_chats(update, context):
            return False
    return True

### --- Check is user has active chat with bot --- ###
async def has_active_private_chat(bot, user_id: int) -> bool:
    try:
        await bot.send_chat_action(chat_id=user_id, action="typing")
        return True
    except Forbidden:
        return False
    except Exception as e:
        return False