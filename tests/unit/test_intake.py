import pytest

from bot_atul.services.tickets import IntakeSession, IntakeStep


def test_guided_intake_preserves_multi_message_description() -> None:
    session = IntakeSession(reporter_id=10, services=("General", "Technical"))

    session.answer("Agent cannot start")
    session.answer("Technical")
    session.answer("High")
    session.answer("First part 🚀")
    session.answer("Second part")
    session.complete_description()
    session.add_attachment("document", "file-123", "trace.txt", None)
    session.finish_attachments()

    assert session.step is IntakeStep.REVIEW
    assert session.description == "First part 🚀\nSecond part"
    assert session.attachments[0].file_id == "file-123"
    assert "Agent cannot start" in session.summary()


@pytest.mark.parametrize("value", ["", "   "])
def test_title_must_not_be_blank(value: str) -> None:
    session = IntakeSession(reporter_id=10, services=("General",))

    with pytest.raises(ValueError, match="title"):
        session.answer(value)


def test_service_and_urgency_must_be_valid() -> None:
    session = IntakeSession(reporter_id=10, services=("General",))
    session.answer("Training failure")

    with pytest.raises(ValueError, match="service"):
        session.answer("Unknown")
    session.answer("General")

    with pytest.raises(ValueError, match="urgency"):
        session.answer("Emergency")


def test_description_is_required() -> None:
    session = IntakeSession(reporter_id=10, services=("General",))
    session.answer("Training failure")
    session.answer("General")
    session.answer("Normal")

    with pytest.raises(ValueError, match="description"):
        session.complete_description()
