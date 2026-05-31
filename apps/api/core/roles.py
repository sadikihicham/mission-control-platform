"""RBAC — rôles et hiérarchie (Contract B étendu). Owner : `security` (M9).

Hiérarchie (du moins au plus privilégié) :
    viewer < developer < pm < cto < admin
`require_role(min)` autorise tout rôle de niveau >= min.
"""
import enum


class Role(str, enum.Enum):
    viewer = "viewer"
    developer = "developer"
    pm = "pm"
    cto = "cto"
    admin = "admin"


# Niveau numérique pour comparer.
LEVEL: dict[str, int] = {
    Role.viewer: 0,
    Role.developer: 1,
    Role.pm: 2,
    Role.cto: 3,
    Role.admin: 4,
}


def level_of(role: str) -> int:
    try:
        return LEVEL[Role(role)]
    except ValueError:
        return -1  # rôle inconnu → moins que viewer


def has_at_least(role: str, minimum: Role) -> bool:
    return level_of(role) >= LEVEL[minimum]
