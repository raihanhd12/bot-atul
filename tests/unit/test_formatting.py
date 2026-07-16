from bot_atul.db.repositories import Ticket
from bot_atul.telegram.formatting import description_chunks, ticket_card, topic_title


def ticket(**changes: object) -> Ticket:
    values: dict[str, object] = {
        "number": 42,
        "reporter_id": 10,
        "service_name": "AI-Agents",
        "urgency": "High",
        "title": "Agent cannot start",
        "description": "Detailed failure",
        "status": "Open",
        "topic_id": None,
        "card_message_id": None,
    }
    values.update(changes)
    return Ticket(**values)  # type: ignore[arg-type]


def test_topic_title_is_bounded() -> None:
    result = topic_title(ticket(title="x" * 200))

    assert len(result) <= 128
    assert result.endswith("… · Open")


def test_description_chunks_are_lossless() -> None:
    description = ("long line 🚀\n" * 1_000).rstrip()
    chunks = description_chunks(description, limit=200)

    assert "".join(chunks) == description
    assert all(len(chunk) <= 200 for chunk in chunks)


def test_ticket_card_contains_required_fields() -> None:
    card = ticket_card(ticket())

    assert "#42" in card
    assert "AI-Agents" in card
    assert "High" in card
    assert "Open" in card
    assert "Reporter: 10" in card
