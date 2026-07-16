from typing import Any

from bot_atul.db.repositories import Repository, Ticket
from bot_atul.telegram.formatting import (
    description_chunks,
    ticket_card,
    topic_title,
)


async def create_ticket_topic(
    bot: Any, repository: Repository, team_group_id: int, ticket: Ticket
) -> int:
    topic_id = ticket.topic_id
    if topic_id is None:
        topic = await bot.create_forum_topic(
            chat_id=team_group_id, name=topic_title(ticket)
        )
        topic_id = int(topic.message_thread_id)
        repository.attach_topic(ticket.number, topic_id)

    if ticket.card_message_id is None:
        card = await bot.send_message(
            chat_id=team_group_id,
            message_thread_id=topic_id,
            text=ticket_card(ticket),
        )
        repository.attach_card(ticket.number, int(card.message_id))
        chunks = description_chunks(ticket.description)
        for index, chunk in enumerate(chunks, start=1):
            await bot.send_message(
                chat_id=team_group_id,
                message_thread_id=topic_id,
                text=f"Description ({index}/{len(chunks)})\n{chunk}",
            )
        for kind, file_id, _file_name, caption in repository.list_attachments(
            ticket.number
        ):
            method = bot.send_photo if kind == "photo" else bot.send_document
            await method(
                chat_id=team_group_id,
                message_thread_id=topic_id,
                **{kind: file_id},
                caption=caption,
            )
    return topic_id
