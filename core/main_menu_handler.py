from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from core.config_loader import CFG, TEXTS

class MainMenu:
    def __init__(self):
        pass

    def _keyboard(self):
        button_text = TEXTS["main_menu"]["buttons"]
        rows = [
            [InlineKeyboardButton(button_text["search"], switch_inline_query_current_chat="")],
            [InlineKeyboardButton(button_text["help"], callback_data="mainmenu_help", api_kwargs={"style": "primary"})]
        ]
        return InlineKeyboardMarkup(rows)

    async def show(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        main_menu_text = TEXTS["main_menu"]["title"].format(version=CFG["VERSION"])
        if update.callback_query:
            await update.callback_query.edit_message_text(main_menu_text, reply_markup=self._keyboard(), parse_mode="HTML")
        else:
            await update.effective_chat.send_message(main_menu_text, reply_markup=self._keyboard(), parse_mode="HTML")

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = TEXTS["help"].format(version=CFG["VERSION"])
        if update.callback_query:
            await update.callback_query.edit_message_text(help_text, 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(TEXTS["backtomain"], callback_data="mainmenu_show")]]),
                parse_mode="HTML"
            )
        else:
            await update.effective_chat.send_message(help_text, 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(TEXTS["backtomain"], callback_data="mainmenu_show")]]),
                parse_mode="HTML"
            )

    async def callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        data = query.data or ""

        if data == "mainmenu_show":
            await self.show(update, context)
            return
        
        elif data == "mainmenu_help":
            await self.help(update, context)
            return