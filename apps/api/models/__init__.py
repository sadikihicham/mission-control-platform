"""Modèles core MVP (Contract A). Owner : agent `db-core`.

Import canonique : `from apps.api.models import User, Project, Agent, Task, ActivityLog`
"""
from apps.api.models.agent_control import (
    LOCAL_INSTALLATION_ID,
    LOCAL_INSTALLATION_KEY,
    AgentCommand,
    AgentCredential,
    AgentEvent,
    AgentPolicy,
    AgentProjectAssignment,
    AgentRun,
    AgentRunStep,
    ApprovalRequest,
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
    "AgentPolicy",
    "AgentProjectAssignment",
    "AgentRun",
    "AgentRunStep",
    "AgentCommand",
    "ApprovalRequest",
    "MCOutboxEvent",
    "LOCAL_INSTALLATION_ID",
    "LOCAL_INSTALLATION_KEY",
]
