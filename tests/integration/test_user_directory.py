import sqlite3

from bot_atul.db.migrations import migrate
from bot_atul.db.repositories import Repository


def test_user_directory_lists_roles_and_remembered_names() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    migrate(connection)
    repository = Repository(connection)
    repository.upsert_user(10, "admin")
    repository.upsert_user(20, "agent")
    repository.upsert_user(30, "agent")
    repository.remember_user(20, "andi", "Andi Agent")

    team = repository.list_users(("admin", "agent"))
    by_id = {user.telegram_id: user for user in team}

    assert set(by_id) == {10, 20, 30}
    assert by_id[10].role == "admin"
    assert by_id[20].role == "agent"
    assert by_id[30].role == "agent"
    assert by_id[20].display_name == "Andi Agent"
    assert by_id[20].username == "andi"
    assert team[0].telegram_id == 10


def test_legacy_reporters_are_promoted_to_agents() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE users (
            telegram_id INTEGER PRIMARY KEY,
            role TEXT NOT NULL CHECK (role IN ('reporter', 'agent', 'admin')),
            username TEXT,
            display_name TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO users(telegram_id, role) VALUES (40, 'reporter');
        """
    )
    migrate(connection)
    repository = Repository(connection)

    assert repository.get_role(40) == "agent"
