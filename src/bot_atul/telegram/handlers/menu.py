from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot_atul.db.repositories import Repository
from bot_atul.telegram.menu import (
    ADMIN_HELP,
    HELP,
    MY_TICKETS,
    TEAM_HELP,
    main_menu,
    welcome_text,
)


def build_menu_router(repository: Repository) -> Router:
    router = Router(name="menu")

    @router.message(Command("start"))
    async def start(message: Message) -> None:
        if message.from_user is None:
            return
        role = repository.get_role(message.from_user.id)
        if role is None:
            await message.answer(
                "You are not approved yet. Ask an admin to add your Telegram user ID."
            )
            return
        await message.answer(welcome_text(role), reply_markup=main_menu(role))

    @router.message(F.text == MY_TICKETS)
    async def my_tickets(message: Message) -> None:
        if message.from_user is None:
            return
        tickets = repository.active_tickets(message.from_user.id)
        if not tickets:
            await message.answer("You have no active tickets.")
            return
        await message.answer(
            "\n".join(
                f"#{ticket.number} · {ticket.status} · "
                f"{ticket.service_name} · {ticket.title}"
                for ticket in tickets
            )
        )

    @router.message(F.text == HELP)
    async def help_message(message: Message) -> None:
        await message.answer(
            "Use Report Issue to create a ticket. "
            "Use My Tickets to view your active reports."
        )

    @router.message(F.text == TEAM_HELP)
    async def team_help(message: Message) -> None:
        if not _has_role(repository, message, {"agent", "admin"}):
            return
        await message.answer(
            "In a ticket topic, reply directly to a relayed reporter message, "
            "or use /reply <message>. Use the ticket buttons to assign and "
            "update status."
        )

    @router.message(F.text == ADMIN_HELP)
    async def admin_help(message: Message) -> None:
        if not _has_role(repository, message, {"admin"}):
            return
        await message.answer(
            "Admin commands:\n"
            "/user_add <id> <reporter|agent|admin>\n"
            "/user_disable <id>\n"
            "/service_add <name>\n"
            "/service_rename <old> <new>\n"
            "/service_disable <name>\n"
            "/service_move <name> <position>\n"
            "/export [start] [end]"
        )

    return router


def _has_role(repository: Repository, message: Message, roles: set[str]) -> bool:
    return (
        message.from_user is not None
        and repository.get_role(message.from_user.id) in roles
    )
