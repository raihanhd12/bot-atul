import sqlite3

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot_atul.db.repositories import Repository

COMMANDS = (
    "user_add",
    "user_disable",
    "service_add",
    "service_rename",
    "service_disable",
    "service_move",
)


def build_admin_router(repository: Repository) -> Router:
    router = Router(name="admin")

    @router.message(Command(*COMMANDS))
    async def admin_command(message: Message) -> None:
        if message.from_user is not None and message.text is not None:
            response = execute_admin_command(
                repository, message.from_user.id, message.text
            )
            await message.answer(response)

    return router


def execute_admin_command(repository: Repository, actor_id: int, command: str) -> str:
    if repository.get_role(actor_id) != "admin":
        return "Not allowed."

    parts = command.split()
    name = parts[0] if parts else ""
    try:
        if name == "/user_add" and len(parts) == 3:
            telegram_id = int(parts[1])
            repository.upsert_user(telegram_id, parts[2])
            return _success(
                repository,
                actor_id,
                command,
                f"User {telegram_id} saved as {parts[2]}.",
            )
        if name == "/user_disable" and len(parts) == 2:
            telegram_id = int(parts[1])
            repository.disable_user(telegram_id)
            return _success(
                repository, actor_id, command, f"User {telegram_id} disabled."
            )
        if name == "/service_add" and len(parts) == 2:
            repository.add_service(parts[1])
            return _success(repository, actor_id, command, f"Service {parts[1]} added.")
        if name == "/service_rename" and len(parts) == 3:
            repository.rename_service(parts[1], parts[2])
            return _success(
                repository,
                actor_id,
                command,
                f"Service {parts[1]} renamed to {parts[2]}.",
            )
        if name == "/service_disable" and len(parts) == 2:
            repository.disable_service(parts[1])
            return _success(
                repository, actor_id, command, f"Service {parts[1]} disabled."
            )
        if name == "/service_move" and len(parts) == 3:
            position = int(parts[2])
            repository.move_service(parts[1], position)
            return _success(
                repository,
                actor_id,
                command,
                f"Service {parts[1]} moved to position {position}.",
            )
    except (ValueError, sqlite3.IntegrityError):
        pass

    return _usage(name)


def _success(repository: Repository, actor_id: int, command: str, response: str) -> str:
    repository.record_audit(actor_id, "admin_command", command)
    return response


def _usage(command: str) -> str:
    usages = {
        "/user_add": "Usage: /user_add <telegram_id> <agent|admin>",
        "/user_disable": "Usage: /user_disable <telegram_id>",
        "/service_add": "Usage: /service_add <name>",
        "/service_rename": "Usage: /service_rename <old> <new>",
        "/service_disable": "Usage: /service_disable <name>",
        "/service_move": "Usage: /service_move <name> <position>",
    }
    return usages.get(command, "Unknown admin command.")
