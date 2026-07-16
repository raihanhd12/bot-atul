import sqlite3

import pytest

from bot_atul.db.migrations import migrate
from bot_atul.db.repositories import Repository
from bot_atul.telegram.handlers.admin import execute_admin_command


@pytest.fixture
def repository() -> Repository:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    repository = Repository(connection)
    repository.upsert_user(1, "admin")
    repository.upsert_user(2, "agent")
    return repository


def test_admin_can_manage_allowlist(repository: Repository) -> None:
    result = execute_admin_command(repository, 1, "/user_add 10 reporter")
    assert result == "User 10 saved as reporter."
    assert repository.get_role(10) == "reporter"

    assert (
        execute_admin_command(repository, 1, "/user_disable 10") == "User 10 disabled."
    )
    assert repository.get_role(10) is None


def test_non_admin_is_rejected(repository: Repository) -> None:
    assert (
        execute_admin_command(repository, 2, "/user_add 10 reporter") == "Not allowed."
    )
    assert repository.get_role(10) is None


def test_admin_can_manage_services(repository: Repository) -> None:
    assert execute_admin_command(repository, 1, "/service_add AI-Search") == (
        "Service AI-Search added."
    )
    assert execute_admin_command(repository, 1, "/service_rename AI-Search AI-RAG") == (
        "Service AI-Search renamed to AI-RAG."
    )
    assert execute_admin_command(repository, 1, "/service_move AI-RAG 1") == (
        "Service AI-RAG moved to position 1."
    )
    assert repository.list_services()[0] == "AI-RAG"
    assert execute_admin_command(repository, 1, "/service_disable AI-RAG") == (
        "Service AI-RAG disabled."
    )
    assert "AI-RAG" not in repository.list_services()


def test_bad_admin_command_returns_usage(repository: Repository) -> None:
    assert execute_admin_command(repository, 1, "/user_add nope") == (
        "Usage: /user_add <telegram_id> <reporter|agent|admin>"
    )
