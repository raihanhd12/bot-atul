from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
)


async def register_commands(bot: Bot, admin_ids: frozenset[int]) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Open the interactive menu"),
            BotCommand(command="new", description="Report a new issue"),
        ],
        scope=BotCommandScopeAllPrivateChats(),
    )
    admin_commands = [
        BotCommand(command="start", description="Open the interactive menu"),
        BotCommand(command="new", description="Report a new issue"),
        BotCommand(command="export", description="Export issues to Excel"),
        BotCommand(command="user_add", description="Add an approved user"),
        BotCommand(command="user_disable", description="Disable an approved user"),
        BotCommand(command="service_add", description="Add a category"),
        BotCommand(command="service_rename", description="Rename a category"),
        BotCommand(command="service_disable", description="Disable a category"),
        BotCommand(command="service_move", description="Reorder a category"),
    ]
    for admin_id in admin_ids:
        await bot.set_my_commands(
            admin_commands, scope=BotCommandScopeChat(chat_id=admin_id)
        )
