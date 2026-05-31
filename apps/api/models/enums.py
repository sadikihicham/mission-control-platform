"""Enums métier — figés par le Contract A."""
import enum


class ProjectStatus(str, enum.Enum):
    proposed = "proposed"
    validated = "validated"
    in_dev = "in_dev"
    done = "done"
    archived = "archived"


class AgentState(str, enum.Enum):
    idle = "idle"
    working = "working"
    blocked = "blocked"
    done = "done"
    error = "error"
    stale = "stale"
