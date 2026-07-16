from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu(role: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="📝 Report Issue", callback_data="menu:report"),
            InlineKeyboardButton(text="📋 My Tickets", callback_data="menu:tickets"),
        ],
        [InlineKeyboardButton(text="❓ Help", callback_data="menu:help")],
    ]
    if role in {"agent", "admin"}:
        rows.append(
            [InlineKeyboardButton(text="👥 Team Help", callback_data="menu:team_help")]
        )
    if role == "admin":
        rows.append(
            [
                InlineKeyboardButton(
                    text="📤 Export Excel", callback_data="dashboard:export"
                ),
                InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin:home"),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_button(target: str = "menu:home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="← Back", callback_data=target)]]
    )


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧩 Services", callback_data="admin:services"
                ),
                InlineKeyboardButton(
                    text="👥 Team Members", callback_data="admin:team"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👤 Reporters", callback_data="admin:reporters"
                ),
                InlineKeyboardButton(
                    text="⏰ Reminder", callback_data="admin:reminder"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📤 Export Excel", callback_data="dashboard:export"
                )
            ],
            [InlineKeyboardButton(text="← Main Menu", callback_data="menu:home")],
        ]
    )


def service_menu(services: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"admin:service:select:{index}")]
        for index, name in enumerate(services)
    ]
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="＋ Add Service", callback_data="admin:service:add"
                )
            ],
            [InlineKeyboardButton(text="← Admin Panel", callback_data="admin:home")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def service_actions(position: int, total: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="✏️ Rename", callback_data="admin:service:rename"),
            InlineKeyboardButton(
                text="🚫 Disable", callback_data="admin:service:disable"
            ),
        ]
    ]
    moves = []
    if position > 0:
        moves.append(
            InlineKeyboardButton(
                text="⬆️ Move Up", callback_data="admin:service:move_up"
            )
        )
    if position < total - 1:
        moves.append(
            InlineKeyboardButton(
                text="⬇️ Move Down", callback_data="admin:service:move_down"
            )
        )
    if moves:
        rows.append(moves)
    rows.append(
        [
            InlineKeyboardButton(
                text="← Back to Services", callback_data="admin:services"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def service_disable_confirmation() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Yes, Disable",
                    callback_data="admin:service:disable_confirm",
                ),
                InlineKeyboardButton(
                    text="Cancel", callback_data="admin:service:disable_cancel"
                ),
            ]
        ]
    )


def service_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Cancel", callback_data="admin:service:cancel")]
        ]
    )


def user_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="＋ Add User", callback_data="admin:hint:user_add"
                ),
                InlineKeyboardButton(
                    text="🚫 Disable User", callback_data="admin:hint:user_disable"
                ),
            ],
            [InlineKeyboardButton(text="← Admin Panel", callback_data="admin:home")],
        ]
    )


def welcome_text(role: str) -> str:
    return (
        "Welcome to the issue bot.\n"
        f"Your role: {role.title()}.\n"
        "Choose an action below. This message acts as your dashboard."
    )
