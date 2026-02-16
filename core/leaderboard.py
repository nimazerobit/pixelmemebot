from telegram import Update
from telegram.ext import ContextTypes

from container import status_service
from core.config_loader import TEXTS
from core.utils import to_persian_digits, get_persian_datetime_text, check_user

async def leaderboard_text(command_user_id: int):
    top_publishers = await status_service.get_top_publishers()

    if not top_publishers:
        return TEXTS["meme"]["leaderboard"]["empty"]

    text = TEXTS["meme"]["leaderboard"]["header"].format(date=get_persian_datetime_text())

    in_leaderboard = False

    for user_id, meme_count, rank in top_publishers:
        is_me = user_id == command_user_id
        fire = "🔥" if rank == 1 else ""
        pointer = "(شما)" if is_me else ""
        badge = f"{fire} {pointer}".strip()

        if is_me:
            in_leaderboard = True

        text += (
            f"{to_persian_digits(rank)}. "
            f"{user_id} - "
            f"{to_persian_digits(meme_count)} میم "
            f"{badge}\n"
        )

    if not in_leaderboard:
        my_rank = await status_service.get_publisher_rank(command_user_id)
        if my_rank:
            user_id, meme_count, rank = my_rank
            text += ("\n➖➖➖➖➖\n"
                f"{to_persian_digits(rank)}. "
                f"{user_id} - "
                f"{to_persian_digits(meme_count)} میم"
                f"(شما)\n"
            )

    return text

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user(update, context):
        return
    await update.effective_chat.send_message(
        await leaderboard_text(command_user_id=update.effective_user.id), parse_mode="HTML"
    )