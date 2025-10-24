
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def rating_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="⭐️", callback_data="rate:1"),
         InlineKeyboardButton(text="⭐️⭐️", callback_data="rate:2"),
         InlineKeyboardButton(text="⭐️⭐️⭐️", callback_data="rate:3"),
         InlineKeyboardButton(text="⭐️⭐️⭐️⭐️", callback_data="rate:4"),
         InlineKeyboardButton(text="⭐️⭐️⭐️⭐️⭐️", callback_data="rate:5")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def skip_comment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Пропустить", callback_data="skip_comment")
    ]])
