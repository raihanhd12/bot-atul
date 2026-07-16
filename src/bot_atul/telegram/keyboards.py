from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def choices(prefix: str, values: tuple[str, ...]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=value, callback_data=f"{prefix}:{value}")]
            for value in values
        ]
    )


def action(text: str, data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=data)]]
    )


def review_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Submit", callback_data="intake:confirm")],
            [InlineKeyboardButton(text="Cancel", callback_data="intake:cancel")],
        ]
    )
