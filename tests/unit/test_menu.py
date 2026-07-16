from bot_atul.telegram.menu import main_menu, welcome_text


def labels(role: str) -> list[str]:
    return [button.text for row in main_menu(role).keyboard for button in row]


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
        "⚙️ Admin Help",
    ]
    assert "admin" in welcome_text("admin").lower()
