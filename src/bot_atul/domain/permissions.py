from enum import StrEnum


class Role(StrEnum):
    REPORTER = "reporter"
    AGENT = "agent"
    ADMIN = "admin"


class Action(StrEnum):
    SUBMIT = "submit"
    HANDLE = "handle"
    ADMIN = "admin"


PERMISSIONS = {
    Role.REPORTER: frozenset({Action.SUBMIT}),
    Role.AGENT: frozenset({Action.HANDLE}),
    Role.ADMIN: frozenset({Action.HANDLE, Action.ADMIN}),
}


def allowed(role: Role | None, action: Action) -> bool:
    return role is not None and action in PERMISSIONS[role]
