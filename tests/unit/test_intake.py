from unittest.mock import AsyncMock, Mock, patch
from zoneinfo import ZoneInfo

import pytest
from aiogram.types import Chat, Message, User

from bot_atul.services.tickets import IntakeSession, IntakeStep
from bot_atul.telegram.handlers.intake import (
    SESSIONS,
    begin_intake,
    build_intake_router,
)


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


async def test_title_message_reaches_intake_handler() -> None:
    repository = Mock()
    repository.get_role.return_value = "reporter"
    repository.list_services.return_value = ["AI-ML"]
    begin_intake(repository, 99)
    router = build_intake_router(
        repository, -100, 1, ZoneInfo("Asia/Jakarta")
    )
    message = Message(
        message_id=1,
        date=0,
        chat=Chat(id=99, type="private"),
        from_user=User(id=99, is_bot=False, first_name="Reporter"),
        text="kucing jalanan",
    )

    try:
        with patch.object(Message, "answer", new=AsyncMock()) as answer:
            await router.message.trigger(message, bot=Mock())

        assert answer.await_args.args[0] == "Which service?"
        assert SESSIONS[99].step is IntakeStep.SERVICE
    finally:
        SESSIONS.pop(99, None)
