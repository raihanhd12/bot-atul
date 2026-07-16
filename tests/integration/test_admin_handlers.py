import sqlite3

import pytest

from bot_atul.db.migrations import migrate
from bot_atul.db.repositories import Repository
from bot_atul.telegram.handlers.admin import execute_admin_command
from bot_atul.telegram.handlers.menu import ServiceSession, apply_service_name


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
    assert repository.count_audit_events("admin_command") == 2


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


def test_interactive_service_names_can_contain_spaces(repository: Repository) -> None:
    assert (
        apply_service_name(repository, 1, ServiceSession("add"), "  AI Intelligence  ")
        == "Service AI Intelligence added."
    )
    assert (
        apply_service_name(
            repository,
            1,
            ServiceSession("rename", "AI Intelligence"),
            "AI Knowledge Platform",
        )
        == "Service AI Intelligence renamed to AI Knowledge Platform."
    )
    assert "AI Knowledge Platform" in repository.list_services()
    assert repository.count_audit_events("admin_service") == 2


def test_interactive_service_name_validation(repository: Repository) -> None:
    with pytest.raises(ValueError, match="blank"):
        apply_service_name(repository, 1, ServiceSession("add"), "   ")
    with pytest.raises(ValueError, match="64"):
        apply_service_name(repository, 1, ServiceSession("add"), "x" * 65)
    with pytest.raises(ValueError, match="already exists"):
        apply_service_name(repository, 1, ServiceSession("add"), "General")
    with pytest.raises(PermissionError, match="Not allowed"):
        apply_service_name(repository, 2, ServiceSession("add"), "AI Security")


def test_services_move_one_step(repository: Repository) -> None:
    assert repository.move_service_by("Technical", -1)
    assert repository.list_services()[:2] == ["Technical", "General"]
    assert repository.move_service_by("Technical", -1) is False
    assert repository.move_service_by("Technical", 1)
    assert repository.list_services()[:2] == ["General", "Technical"]
