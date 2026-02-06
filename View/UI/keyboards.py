from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu(is_running: bool) -> InlineKeyboardMarkup:
    if is_running:
        keyboard = [
            [InlineKeyboardButton("⏹ Stop trading", callback_data="STOP")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("▶ Start trading", callback_data="START")]
        ]

    return InlineKeyboardMarkup(keyboard)