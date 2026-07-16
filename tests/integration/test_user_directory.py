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
    repository.upsert_user(30, "reporter")
    repository.remember_user(20, "andi", "Andi Agent")

    team = repository.list_users(("admin", "agent"))
    reporters = repository.list_users(("reporter",))

    assert [(user.telegram_id, user.role) for user in team] == [
        (10, "admin"),
        (20, "agent"),
    ]
    assert team[1].display_name == "Andi Agent"
    assert team[1].username == "andi"
    assert reporters[0].telegram_id == 30
