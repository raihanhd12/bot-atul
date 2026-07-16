from bot_atul.db.repositories import AttachmentRecord, Ticket
from bot_atul.telegram.keyboards import (
    admin_open_ticket_actions,
    agent_ticket_actions,
    dashboard_ticket_actions,
)
from bot_atul.telegram.menu import (
    admin_menu,
    main_menu,
    service_actions,
    service_disable_confirmation,
    service_menu,
    welcome_text,
)


def labels(role: str) -> list[str]:
    return [button.text for row in main_menu(role).inline_keyboard for button in row]


def test_agent_menu_includes_team_help() -> None:
    assert labels("agent") == [
        "📝 Report Issue",
        "📋 My Tickets",
        "❓ Help",
        "👥 Team Help",
    ]


def test_admin_menu_includes_admin_actions() -> None:
    assert labels("admin") == [
        "📝 Report Issue",
        "📋 My Tickets",
        "❓ Help",
        "👥 Team Help",
        "📤 Export Excel",
        "⚙️ Admin Panel",
    ]
    assert "admin" in welcome_text("admin").lower()


def test_service_menu_lists_services_as_buttons() -> None:
    menu = service_menu(["General", "AI Intelligence"])

    assert [button.text for row in menu.inline_keyboard for button in row] == [
        "General",
        "AI Intelligence",
        "＋ Add Service",
        "← Admin Panel",
    ]
    assert menu.inline_keyboard[1][0].callback_data == "admin:service:select:1"


def test_service_actions_hide_boundary_moves() -> None:
    first = service_actions(0, 3)
    middle = service_actions(1, 3)
    last = service_actions(2, 3)

    assert "⬆️ Move Up" not in _keyboard_labels(first)
    assert "⬇️ Move Down" in _keyboard_labels(first)
    assert {"⬆️ Move Up", "⬇️ Move Down"} <= set(_keyboard_labels(middle))
    assert "⬆️ Move Up" in _keyboard_labels(last)
    assert "⬇️ Move Down" not in _keyboard_labels(last)


def test_disable_requires_confirmation() -> None:
    assert _keyboard_labels(service_disable_confirmation()) == [
        "Yes, Disable",
        "Cancel",
    ]


def test_dashboard_cards_are_view_only_with_details_toggle() -> None:
    open_ticket = Ticket(
        number=1,
        reporter_id=10,
        service_name="General",
        urgency="Normal",
        title="Open work",
        description="Details",
        status="Open",
        topic_id=None,
        card_message_id=None,
        assignee_id=None,
    )
    closed_ticket = Ticket(
        number=2,
        reporter_id=10,
        service_name="General",
        urgency="Normal",
        title="Done",
        description="Done",
        status="Closed",
        topic_id=None,
        card_message_id=None,
        assignee_id=None,
    )

    open_labels = _keyboard_labels(dashboard_ticket_actions(open_ticket))
    closed_labels = _keyboard_labels(dashboard_ticket_actions(closed_ticket))
    detailed_labels = _keyboard_labels(
        dashboard_ticket_actions(open_ticket, detailed=True)
    )
    with_files = _keyboard_labels(
        dashboard_ticket_actions(
            open_ticket,
            detailed=True,
            attachments=[
                AttachmentRecord(1, "photo", "x", None, None),
            ],
        )
    )

    assert open_labels == ["📄 View Details"]
    assert closed_labels == ["📄 View Details"]
    assert detailed_labels == ["▲ Hide Details"]
    assert "Show 1 file(s)" in " ".join(with_files)
    assert "Assign" not in " ".join(open_labels)
    assert "Close" not in " ".join(open_labels)


def test_self_owned_workspace_hides_reply_to_reporter() -> None:
    ticket = Ticket(
        number=1,
        reporter_id=10,
        service_name="General",
        urgency="Normal",
        title="Mine",
        description="Details",
        status="Open",
        topic_id=None,
        card_message_id=None,
        assignee_id=10,
    )
    labels = _keyboard_labels(agent_ticket_actions(ticket))
    assert "Reply to Reporter" not in labels
    assert "Start Work" in labels
    assert "Close" in labels


def test_admin_menu_includes_open_tickets() -> None:
    labels = [
        button.text for row in admin_menu().inline_keyboard for button in row
    ]
    assert "📂 Open Tickets" in labels


def test_admin_open_ticket_actions_offer_close() -> None:
    ticket = Ticket(
        number=3,
        reporter_id=10,
        service_name="General",
        urgency="High",
        title="Broken deploy",
        description="Details",
        status="In Progress",
        topic_id=None,
        card_message_id=None,
        assignee_id=10,
    )
    labels = _keyboard_labels(admin_open_ticket_actions([ticket]))
    assert any(label.startswith("Close #3") for label in labels)


def _keyboard_labels(menu: object) -> list[str]:
    assert hasattr(menu, "inline_keyboard")
    return [
        button.text
        for row in menu.inline_keyboard  # type: ignore[attr-defined]
        for button in row
    ]
