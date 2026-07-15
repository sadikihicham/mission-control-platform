"""Modèles core MVP (Contract A). Owner : agent `db-core`.

Import canonique : `from apps.api.models import User, Project, Agent, Task, ActivityLog`
"""
from apps.api.models.agent_control import (
    LOCAL_INSTALLATION_ID,
    LOCAL_INSTALLATION_KEY,
    AgentCredential,
    AgentEvent,
    AgentProjectAssignment,
    AgentRun,
    AgentRunStep,
    MCInstallation,
    MCOutboxEvent,
    MCUserMapping,
)
from apps.api.models.enums import AgentState, ProjectStatus
from apps.api.models.tables import (
    ActivityLog,
    Agent,
    PasswordResetToken,
    Project,
    Task,
    User,
)

__all__ = [
    "User",
    "Project",
    "Agent",
    "Task",
    "ActivityLog",
    "PasswordResetToken",
    "ProjectStatus",
    "AgentState",
    "MCInstallation",
    "MCUserMapping",
    "AgentCredential",
    "AgentEvent",
    "AgentProjectAssignment",
    "AgentRun",
    "AgentRunStep",
    "MCOutboxEvent",
    "LOCAL_INSTALLATION_ID",
    "LOCAL_INSTALLATION_KEY",
]
