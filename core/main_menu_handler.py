from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from core.config_loader import CFG, TEXTS

### --- Main Menu --- ###
def main_menu_keyboard():
    button_text = TEXTS["main_menu"]["buttons"]
    rows = [
        [InlineKeyboardButton(button_text["search"], switch_inline_query_current_chat="")],
        [InlineKeyboardButton(button_text["help"], callback_data="help")]
    ]
    return InlineKeyboardMarkup(rows)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    main_menu_text = TEXTS["main_menu"]["title"].format(version=CFG["VERSION"])
    if edit or update.callback_query:
        await update.callback_query.edit_message_text(f'{main_menu_text}', reply_markup=main_menu_keyboard(), parse_mode="HTML")
    else:
        await update.effective_chat.send_message(f'{main_menu_text}', reply_markup=main_menu_keyboard(), parse_mode="HTML")

### --- Main Menu Callbacks --- ###
async def main_menu_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    user_id = update.effective_user.id

    if data == "backtomain":
        await show_main_menu(update, context, edit=True)
        return
    
    elif data == "help":
        await query.edit_message_text(
            TEXTS["help"].format(version=CFG["VERSION"]), 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(TEXTS["backtomain"], callback_data="backtomain")]]),
            parse_mode="HTML"
        )
        return