from enum import StrEnum


class Role(StrEnum):
    AGENT = "agent"
    ADMIN = "admin"


class Action(StrEnum):
    SUBMIT = "submit"
    HANDLE = "handle"
    ADMIN = "admin"


PERMISSIONS = {
    Role.AGENT: frozenset({Action.SUBMIT, Action.HANDLE}),
    Role.ADMIN: frozenset({Action.SUBMIT, Action.HANDLE, Action.ADMIN}),
}

VALID_ROLES = frozenset({role.value for role in Role})


def allowed(role: Role | None, action: Action) -> bool:
    return role is not None and action in PERMISSIONS[role]
