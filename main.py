from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, InlineQueryHandler, ChosenInlineResultHandler, ConversationHandler, MessageHandler, filters

from core.config_loader import CFG, TEXTS
from core.admin_system import show_all_users, admin_userinfo, adminpanel, broadcast, admin_callbacks
from core.main_menu_handler import show_main_menu, main_menu_callbacks
from core.utils import check_user
from core.meme_module import *
from core.meme_admin import get_meme, meme_admin_callbacks, edit_title, edit_tags
from core.leaderboard import LeaderBoard
from core.convert_to_voice import convert_to_voice

# start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ["group", "supergroup", "channel"]:
        return
    if not await check_user(update, context):
        return
    
    args = context.args
    if args:
        pass

    await show_main_menu(update, context)

# dev command
async def developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user(update, context):
        return
    message_id = update.effective_message.message_id
    await update.effective_chat.send_sticker("CAACAgQAAxkBAAEYQ2VoyzUvLPliEpY_GyNMY7xdu6zd-gAC_RoAArthMFIYwE-KUPkN9zYE", reply_to_message_id=message_id)
    await update.effective_chat.send_message(text=TEXTS["dev"].format(version=CFG["VERSION"]), reply_to_message_id=message_id, parse_mode="HTML")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTS["cancel"], reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ——— Global Callbacks ———
async def global_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    # user_id = update.effective_user.id

    # Empty Callback
    if data == "emptycallback":
        await query.answer(r"¯\_(ツ)_/¯")
        return

# ——— App bootstrap ———
def main():
    token = CFG["BOT_TOKEN"]
    app = Application.builder().token(token).build()

    # Init
    leaderboard = LeaderBoard()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dev", developer))
    app.add_handler(CommandHandler("voice", convert_to_voice))
    app.add_handler(CommandHandler("leaderboard", leaderboard.show))

    app.add_handler(CommandHandler("user", admin_userinfo))
    app.add_handler(CommandHandler("users", show_all_users))
    app.add_handler(CommandHandler("adminpanel", adminpanel))
    app.add_handler(CommandHandler("broadcast", broadcast))

    app.add_handler(CommandHandler("get_meme", get_meme))
    app.add_handler(CommandHandler("edit_title", edit_title))
    app.add_handler(CommandHandler("edit_tags", edit_tags))

    # Callbacks
    app.add_handler(CallbackQueryHandler(main_menu_callbacks, pattern=r"^(backtomain|help)"))
    app.add_handler(CallbackQueryHandler(global_callbacks, pattern=r"^(emptycallback)$"))
    app.add_handler(CallbackQueryHandler(meme_admin_callbacks, pattern=r"^(admin_delete_meme|admin_ban_meme)"))
    app.add_handler(CallbackQueryHandler(admin_meme_decision, pattern="^admin_vote:"))
    app.add_handler(CallbackQueryHandler(admin_callbacks, pattern=r"^(admin_|reload_)"))
    app.add_handler(CallbackQueryHandler(meme_vote, pattern="^meme_vote:"))
    app.add_handler(CallbackQueryHandler(meme_confirm, pattern="^meme_"))

    # Inline query
    app.add_handler(InlineQueryHandler(inline_meme_search))
    app.add_handler(ChosenInlineResultHandler(on_meme_chosen))

    # Conversations
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("new", new_meme)],
        states={
            MEDIA: [MessageHandler(filters.VIDEO | filters.VOICE | filters.AUDIO & ~filters.COMMAND, get_media)],
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tags)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    print("Bot started")

    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
