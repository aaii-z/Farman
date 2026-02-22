from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel


class AgentTask(BaseModel):
    ticket_id: str
    title: str
    description: str
    labels: list[str]
    reporter: str
    assignee: str


class ParsedIntent(BaseModel):
    action: str
    target: str
    environment: str
    hosts: list[str]
    parameters: dict[str, Any] = {}


class Artifact(BaseModel):
    content: str
    risk_level: Literal["read_only", "low", "high", "destructive"]
    explanation: str
    module_name: str


class BaseModule(ABC):
    name: str = ""

    @abstractmethod
    def can_handle(self, labels: list[str], intent: ParsedIntent) -> bool:
        """Return True if this module should handle the given labels/intent."""

    @abstractmethod
    def generate(self, task: AgentTask, intent: ParsedIntent) -> Artifact:
        """Generate an artifact for the task. Must be side-effect-free."""

    @abstractmethod
    def execute(self, artifact: Artifact, task: AgentTask) -> str:
        """Execute the artifact. Returns a human-readable result string."""
