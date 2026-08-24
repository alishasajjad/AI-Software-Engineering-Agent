import uuid
from dataclasses import dataclass, field

from app.tools.repository import SecureWorkspace


@dataclass
class EngineeringAgentContext:
    task_id: uuid.UUID
    task_title: str
    task_description: str
    workspace: SecureWorkspace

    repository_tool_calls: int = 0
    max_repository_tool_calls: int = 6

    repository_evidence: list[str] = field(
        default_factory=list,
    )

    seen_repository_calls: set[str] = field(
        default_factory=set,
    )