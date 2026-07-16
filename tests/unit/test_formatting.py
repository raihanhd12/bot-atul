from bot_atul.db.repositories import AttachmentRecord, Ticket
from bot_atul.telegram.formatting import description_chunks, ticket_card


def ticket(**changes: object) -> Ticket:
    values: dict[str, object] = {
        "number": 42,
        "reporter_id": 10,
        "service_name": "Technical",
        "urgency": "High",
        "title": "Agent cannot start",
        "description": "Detailed failure",
        "status": "Open",
        "topic_id": None,
        "card_message_id": None,
        "assignee_id": None,
    }
    values.update(changes)
    return Ticket(**values)  # type: ignore[arg-type]


def test_description_chunks_are_lossless() -> None:
    description = ("long line 🚀\n" * 1_000).rstrip()
    chunks = description_chunks(description, limit=200)

    assert "".join(chunks) == description
    assert all(len(chunk) <= 200 for chunk in chunks)


def test_ticket_card_uses_status_icons_and_names() -> None:
    card = ticket_card(
        ticket(status="Closed", assignee_id=10, urgency="Critical"),
        names={10: "Raihan (@raihan)"},
    )

    assert "✅ Ticket #42 · Closed" in card
    assert "🚨 Urgency   Critical" in card
    assert "👤 By        Raihan (@raihan)" in card
    assert "Reported" not in card
    assert "Owner" not in card
    assert "Agent cannot start" in card
    assert "Detailed failure" not in card


def test_ticket_card_by_prefers_assignee_when_set() -> None:
    card = ticket_card(
        ticket(assignee_id=20),
        names={10: "Raihan (@raihan)", 20: "Andi (@andi)"},
    )

    assert "👤 By        Andi (@andi)" in card
    assert "Reported" not in card
    assert "Owner" not in card


def test_ticket_card_detailed_includes_description_and_attachments() -> None:
    attachments = [
        AttachmentRecord(1, "photo", "p1", None, "screen"),
        AttachmentRecord(2, "document", "d1", "report.pdf", None),
    ]
    card = ticket_card(
        ticket(description="Full stack trace here"),
        names={10: "Andi"},
        detailed=True,
        attachments=attachments,
    )

    assert "📝 Details" in card
    assert "Full stack trace here" in card
    assert "📎 Attachments  2" in card
    assert "🖼️ screen" in card
    assert "📄 report.pdf" in card
    assert "Tap a file button below" in card


def test_summary_shows_attachment_count() -> None:
    attachments = [AttachmentRecord(1, "photo", "p1", None, None)]
    card = ticket_card(ticket(), attachments=attachments)
    assert "📎 Files     1 attachment(s)" in card
