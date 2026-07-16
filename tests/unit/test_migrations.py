import sqlite3

from bot_atul.db.migrations import migrate


def test_migration_creates_schema_and_services() -> None:
    connection = sqlite3.connect(":memory:")

    migrate(connection)
    migrate(connection)

    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert {
        "users",
        "services",
        "tickets",
        "ticket_messages",
        "attachments",
        "assignments",
        "status_history",
        "dashboard_posts",
        "processed_updates",
        "audit_events",
    } <= tables
    services = connection.execute(
        "SELECT name FROM services ORDER BY position"
    ).fetchall()
    assert services == [
        ("General",),
        ("Technical",),
        ("Billing",),
        ("Other",),
    ]
