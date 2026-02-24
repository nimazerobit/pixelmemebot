from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, InlineQueryHandler, ChosenInlineResultHandler, ConversationHandler, MessageHandler, filters
import asyncio

from core.config_loader import CFG, TEXTS
from core.admin_system import AdminPanel
from core.main_menu_handler import MainMenu
from core.utils import check_user
from core.meme_module import *
from core.meme_admin import get_meme, meme_admin_callbacks, edit_title, edit_tags
from core.leaderboard import LeaderBoard
from core.convert_to_voice import convert_to_voice, conversion_worker

# start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ["group", "supergroup", "channel"]:
        return
    if not await check_user(update, context):
        return
    
    main_menu = MainMenu()
    await main_menu.show(update, context)

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
    
# ——— Background Tasks ———
async def post_init(app: Application):
    app.bot_data["conversion_task"] = asyncio.create_task(
        conversion_worker(app)
    )

async def post_shutdown(app: Application):
    task = app.bot_data.get("conversion_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

# ——— App bootstrap ———
def main():
    token = CFG["BOT_TOKEN"]
    app = Application.builder().token(token).post_init(post_init).post_shutdown(post_shutdown).build()

    # Init
    main_menu = MainMenu()
    admin_panel = AdminPanel()
    leaderboard = LeaderBoard()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", main_menu.help))
    app.add_handler(CommandHandler("dev", developer))
    app.add_handler(CommandHandler("voice", convert_to_voice))
    app.add_handler(CommandHandler("leaderboard", leaderboard.show))

    app.add_handler(CommandHandler("user", admin_panel.userinfo))
    app.add_handler(CommandHandler("users", admin_panel.all_users))
    app.add_handler(CommandHandler("adminpanel", admin_panel.show))
    app.add_handler(CommandHandler("broadcast", admin_panel.broadcast))

    app.add_handler(CommandHandler("get_meme", get_meme))
    app.add_handler(CommandHandler("edit_title", edit_title))
    app.add_handler(CommandHandler("edit_tags", edit_tags))

    # Callbacks
    app.add_handler(CallbackQueryHandler(main_menu.callbacks, pattern=r"^(mainmenu_)"))
    app.add_handler(CallbackQueryHandler(global_callbacks, pattern=r"^(emptycallback)$"))
    app.add_handler(CallbackQueryHandler(meme_admin_callbacks, pattern=r"^(admin_delete_meme|admin_ban_meme)"))
    app.add_handler(CallbackQueryHandler(admin_meme_decision, pattern="^admin_vote:"))
    app.add_handler(CallbackQueryHandler(admin_panel.callbacks, pattern=r"^(admin_panel|reload_)"))
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
