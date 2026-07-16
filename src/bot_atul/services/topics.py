from dataclasses import replace
from typing import Any

from aiogram.exceptions import TelegramAPIError

from bot_atul.db.repositories import AttachmentRecord, Repository, Ticket
from bot_atul.telegram.formatting import (
    attachment_label,
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
    attachments = repository.list_attachments(ticket.number)
    if message_id is None:
        card = await bot.send_message(
            chat_id=team_group_id,
            message_thread_id=dashboard_topic_id,
            text=ticket_card(ticket, names=names, attachments=attachments),
            reply_markup=dashboard_ticket_actions(ticket, attachments=attachments),
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
    attachments = repository.list_attachments(ticket.number)
    try:
        await bot.edit_message_text(
            chat_id=team_group_id,
            message_id=message_id,
            text=ticket_card(
                ticket, names=names, detailed=detailed, attachments=attachments
            ),
            reply_markup=dashboard_ticket_actions(
                ticket, detailed=detailed, attachments=attachments
            ),
        )
    except TelegramAPIError as error:
        # Same text/markup is fine (e.g. Clear preview keeps details open).
        if "message is not modified" not in str(error).lower():
            raise


async def publish_topic_attachment(
    bot: Any,
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
    ticket: Ticket,
    attachment_id: int,
    *,
    replace_existing: bool = True,
) -> bool:
    """Post one attachment under the card (temporary preview).

    By default replaces any current preview so only one file is visible —
    keeps the closed issues topic clean and structured.
    """
    card_message_id = repository.get_dashboard_card(ticket.number)
    if card_message_id is None:
        return False
    attachments = repository.list_attachments(ticket.number)
    attachment = next((item for item in attachments if item.id == attachment_id), None)
    if attachment is None:
        return False
    index = next(
        (i for i, item in enumerate(attachments, start=1) if item.id == attachment_id),
        1,
    )
    if replace_existing:
        await hide_topic_attachments(bot, repository, team_group_id, ticket)
    elif repository.is_topic_attachment_posted(attachment.id):
        return True

    label = attachment_label(attachment, index)
    caption = f"#{ticket.number} · {label}"
    if attachment.caption and attachment.caption not in caption:
        caption = f"{caption}\n{attachment.caption}"
    try:
        message = await _send_attachment(
            bot,
            chat_id=team_group_id,
            thread_id=dashboard_topic_id,
            reply_to=card_message_id,
            attachment=attachment,
            caption=caption[:1_024],
        )
    except TelegramAPIError:
        return False
    repository.save_topic_attachment(
        ticket.number, attachment.id, int(message.message_id)
    )
    return True


async def publish_topic_attachments(
    bot: Any,
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
    ticket: Ticket,
) -> int:
    """Post every attachment without replacing (tests / bulk)."""
    for attachment in repository.list_attachments(ticket.number):
        await publish_topic_attachment(
            bot,
            repository,
            team_group_id,
            dashboard_topic_id,
            ticket,
            attachment.id,
            replace_existing=False,
        )
    return len(repository.list_topic_attachment_messages(ticket.number))


async def hide_topic_attachments(
    bot: Any,
    repository: Repository,
    team_group_id: int,
    ticket: Ticket,
) -> int:
    """Delete temporary attachment messages so the topic stays clean."""
    posted = repository.list_topic_attachment_messages(ticket.number)
    if not posted:
        return 0
    removed = 0
    for _attachment_id, message_id in posted:
        try:
            await bot.delete_message(chat_id=team_group_id, message_id=message_id)
            removed += 1
        except TelegramAPIError:
            # Still drop the tracking row so a later View can re-post cleanly.
            continue
    repository.clear_topic_attachments(ticket.number)
    return removed


async def _send_attachment(
    bot: Any,
    *,
    chat_id: int,
    thread_id: int,
    reply_to: int,
    attachment: AttachmentRecord,
    caption: str,
) -> Any:
    common = {
        "chat_id": chat_id,
        "message_thread_id": thread_id,
        "reply_to_message_id": reply_to,
        "caption": caption,
    }
    if attachment.kind == "photo":
        return await bot.send_photo(photo=attachment.file_id, **common)
    return await bot.send_document(document=attachment.file_id, **common)


async def create_agent_workspace(
    bot: Any, repository: Repository, ticket: Ticket, agent_id: int
) -> int:
    workspace = repository.get_agent_workspace(ticket.number)
    assigned = replace(ticket, assignee_id=agent_id)
    if workspace is not None and workspace.agent_id == agent_id:
        return workspace.message_id
    names = await ticket_names(bot, repository, assigned)
    attachments = repository.list_attachments(ticket.number)
    chunks = description_chunks(ticket.description, 3_500)
    card = await bot.send_message(
        chat_id=agent_id,
        text=(
            f"{ticket_card(assigned, names=names, attachments=attachments)}\n\n"
            f"📝 Description\n{chunks[0]}"
        ),
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
    for index, attachment in enumerate(attachments, start=1):
        label = attachment_label(attachment, index)
        try:
            if attachment.kind == "photo":
                await bot.send_photo(
                    chat_id=agent_id,
                    photo=attachment.file_id,
                    caption=attachment.caption or label,
                )
            else:
                await bot.send_document(
                    chat_id=agent_id,
                    document=attachment.file_id,
                    caption=attachment.caption or label,
                )
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
