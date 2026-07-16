from bot_atul.telegram.menu import (
    main_menu,
    service_actions,
    service_disable_confirmation,
    service_menu,
    welcome_text,
)


def labels(role: str) -> list[str]:
    return [button.text for row in main_menu(role).inline_keyboard for button in row]


def test_reporter_menu() -> None:
    assert labels("reporter") == ["📝 Report Issue", "📋 My Tickets", "❓ Help"]


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


def _keyboard_labels(menu: object) -> list[str]:
    assert hasattr(menu, "inline_keyboard")
    return [
        button.text
        for row in menu.inline_keyboard  # type: ignore[attr-defined]
        for button in row
    ]
