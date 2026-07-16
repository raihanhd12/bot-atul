import pytest

from bot_atul.domain.permissions import Action, Role, allowed


@pytest.mark.parametrize(
    ("role", "permitted"),
    [
        (Role.AGENT, {Action.SUBMIT, Action.HANDLE}),
        (Role.ADMIN, {Action.SUBMIT, Action.HANDLE, Action.ADMIN}),
    ],
)
def test_role_matrix(role: Role, permitted: set[Action]) -> None:
    for action in Action:
        assert allowed(role, action) is (action in permitted)


def test_unknown_or_disabled_user_has_no_access() -> None:
    assert allowed(None, Action.SUBMIT) is False
