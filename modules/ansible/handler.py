from __future__ import annotations

import structlog
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from core.llm import get_llm
from config.settings import settings
from modules.base import AgentTask, Artifact, BaseModule, ParsedIntent

log = structlog.get_logger()

_SYSTEM = """\
You are an expert Ansible engineer. Generate a complete, valid Ansible playbook for the DevOps task below.

Rules:
1. Output the playbook YAML in the `playbook` field — no markdown fences, no extra commentary.
2. Use standard built-in Ansible modules. Prefer them over shell/command.
3. Include `become: true` for tasks that require elevated privileges.
4. Set the `hosts` field to the value provided (or "all" if none).
5. Add meaningful task names and tags.
6. Set risk_level based on blast radius:
   - read_only: only gathers information, no changes made
   - low:  safe changes (install/configure on non-prod, idempotent ops)
   - high: changes affecting running services or prod configuration
   - destructive: deletes data, removes packages from prod, rollbacks
7. Write a one-sentence explanation of what the playbook does.
"""

_HUMAN = """\
Task title: {title}
Description: {description}
Action: {action}
Target: {target}
Environment: {environment}
Hosts: {hosts}
Extra parameters: {parameters}
"""

_PROMPT = ChatPromptTemplate.from_messages(
    [("system", _SYSTEM), ("human", _HUMAN)]
)


class _PlaybookOutput(BaseModel):
    playbook: str
    risk_level: Literal["read_only", "low", "high", "destructive"]
    explanation: str


class AnsibleModule(BaseModule):
    name = "ansible"

    def can_handle(self, labels: list[str], intent: ParsedIntent) -> bool:
        return "ansible" in [lbl.lower() for lbl in labels]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def generate(self, task: AgentTask, intent: ParsedIntent) -> Artifact:
        llm = get_llm()
        chain = _PROMPT | llm.with_structured_output(_PlaybookOutput)
        out: _PlaybookOutput = chain.invoke(
            {
                "title": task.title,
                "description": task.description or "(no description provided)",
                "action": intent.action,
                "target": intent.target,
                "environment": intent.environment,
                "hosts": ", ".join(intent.hosts) if intent.hosts else "all",
                "parameters": str(intent.parameters) if intent.parameters else "none",
            }
        )
        log.info(
            "ansible_playbook_generated",
            ticket=task.ticket_id,
            risk=out.risk_level,
        )
        return Artifact(
            content=out.playbook,
            risk_level=out.risk_level,
            explanation=out.explanation,
            module_name=self.name,
        )

    def execute(self, artifact: Artifact, task: AgentTask) -> str:
        # Phase 2: wire up ansible-runner
        # ansible_runner.run(playbook=artifact.content, inventory=..., extravars=...)
        log.info("ansible_execute_stub", ticket=task.ticket_id)
        return "ansible-runner integration pending (Phase 2)"
