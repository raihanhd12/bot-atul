from dataclasses import replace
from typing import Any

from aiogram.exceptions import TelegramAPIError

from bot_atul.db.repositories import Repository, Ticket
from bot_atul.telegram.formatting import (
    description_chunks,
    ticket_card,
)
from bot_atul.telegram.keyboards import agent_ticket_actions, dashboard_ticket_actions


async def refresh_user_profile(
    bot: Any, repository: Repository, telegram_id: int
) -> None:
    """Best-effort username/display-name refresh for nicer topic cards."""
    user = repository.get_user(telegram_id)
    if user is not None and (user.username or user.display_name):
        return
    get_chat = getattr(bot, "get_chat", None)
    if get_chat is None:
        return
    try:
        chat = await get_chat(telegram_id)
    except (TelegramAPIError, TypeError, AttributeError):
        return
    display_name = getattr(chat, "full_name", None) or getattr(chat, "first_name", None)
    if not display_name and not getattr(chat, "username", None):
        return
    repository.remember_user(
        telegram_id,
        getattr(chat, "username", None),
        str(display_name or ""),
    )


async def ticket_names(
    bot: Any, repository: Repository, ticket: Ticket
) -> dict[int, str]:
    ids = {ticket.reporter_id}
    if ticket.assignee_id is not None:
        ids.add(ticket.assignee_id)
    for telegram_id in ids:
        await refresh_user_profile(bot, repository, telegram_id)
    return repository.user_labels(*ids)


async def create_ticket_card(
    bot: Any,
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
    ticket: Ticket,
) -> int:
    ticket = repository.get_ticket(ticket.number) or ticket
    message_id = repository.get_dashboard_card(ticket.number)
    names = await ticket_names(bot, repository, ticket)
    if message_id is None:
        card = await bot.send_message(
            chat_id=team_group_id,
            message_thread_id=dashboard_topic_id,
            text=ticket_card(ticket, names=names),
            reply_markup=dashboard_ticket_actions(ticket),
        )
        message_id = int(card.message_id)
        repository.save_dashboard_card(ticket.number, message_id)
        if ticket.card_message_id is None:
            repository.attach_card(ticket.number, message_id)
    return message_id


async def render_dashboard_card(
    bot: Any,
    repository: Repository,
    team_group_id: int,
    ticket: Ticket,
    *,
    detailed: bool = False,
) -> None:
    message_id = repository.get_dashboard_card(ticket.number)
    if message_id is None:
        return
    names = await ticket_names(bot, repository, ticket)
    await bot.edit_message_text(
        chat_id=team_group_id,
        message_id=message_id,
        text=ticket_card(ticket, names=names, detailed=detailed),
        reply_markup=dashboard_ticket_actions(ticket, detailed=detailed),
    )


async def create_agent_workspace(
    bot: Any, repository: Repository, ticket: Ticket, agent_id: int
) -> int:
    workspace = repository.get_agent_workspace(ticket.number)
    assigned = replace(ticket, assignee_id=agent_id)
    if workspace is not None and workspace.agent_id == agent_id:
        return workspace.message_id
    names = await ticket_names(bot, repository, assigned)
    chunks = description_chunks(ticket.description, 3_500)
    card = await bot.send_message(
        chat_id=agent_id,
        text=f"{ticket_card(assigned, names=names)}\n\n📝 Description\n{chunks[0]}",
        reply_markup=agent_ticket_actions(assigned),
    )
    repository.save_agent_workspace(ticket.number, agent_id, int(card.message_id))
    for index, chunk in enumerate(chunks[1:], start=2):
        try:
            await bot.send_message(
                chat_id=agent_id,
                text=f"Description ({index})\n{chunk}",
            )
        except TelegramAPIError:
            break
    attachments = repository.list_attachments(ticket.number)
    for kind, file_id, _file_name, caption in attachments:
        method = bot.send_photo if kind == "photo" else bot.send_document
        try:
            await method(chat_id=agent_id, **{kind: file_id}, caption=caption)
        except TelegramAPIError:
            continue
    return int(card.message_id)


async def deliver_pending_reporter_messages(
    bot: Any, repository: Repository, ticket: Ticket
) -> None:
    if ticket.assignee_id is None:
        return
    for message in repository.pending_reporter_messages(ticket.number):
        try:
            await bot.send_message(
                chat_id=ticket.assignee_id,
                text=f"Update for ticket #{ticket.number}:",
            )
            copied = await bot.copy_message(
                chat_id=ticket.assignee_id,
                from_chat_id=message.source_chat_id,
                message_id=message.source_message_id,
            )
        except TelegramAPIError:
            await bot.send_message(
                chat_id=ticket.assignee_id,
                text=f"Could not deliver a saved update for ticket #{ticket.number}.",
            )
            continue
        repository.mark_message_sent(
            message.id, ticket.assignee_id, int(copied.message_id)
        )
