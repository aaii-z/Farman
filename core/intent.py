from __future__ import annotations

import structlog
from langchain_core.prompts import ChatPromptTemplate
from tenacity import retry, stop_after_attempt, wait_exponential

from core.llm import get_llm
from config.settings import settings
from modules.base import ParsedIntent

log = structlog.get_logger()

_SYSTEM = """\
You are a DevOps intent parser. Given a Jira ticket, extract structured intent.

Rules:
- action: the primary verb — one of: install, configure, restart, deploy, remove, update, check, rollback, scale
- target: the software or resource (e.g. nginx, postgres, redis, k8s-deployment, terraform-module)
- environment: the target env — one of: dev, staging, prod, all. Default to "dev" if unclear.
- hosts: list of Ansible host groups or IPs. Use ["all"] if not specified.
- parameters: any extra key-value pairs explicitly mentioned (version, port, config values, counts).
"""

_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM),
        (
            "human",
            "Title: {title}\n\nDescription:\n{description}\n\nLabels: {labels}",
        ),
    ]
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def parse_intent(title: str, description: str, labels: list[str]) -> ParsedIntent:
    llm = get_llm()
    chain = _PROMPT | llm.with_structured_output(ParsedIntent)
    result: ParsedIntent = chain.invoke(
        {
            "title": title,
            "description": description or "(no description provided)",
            "labels": ", ".join(labels),
        }
    )
    log.info("intent_parsed", action=result.action, target=result.target, env=result.environment)
    return result
