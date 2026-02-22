from __future__ import annotations

from typing import Any, Optional, TypedDict

import structlog
from langgraph.graph import END, START, StateGraph
from langchain_core.runnables.config import RunnableConfig

from config.settings import settings
from core.approvals import requires_approval
from core.intent import parse_intent
from integrations.jira import JiraClient
from modules.base import Artifact, ParsedIntent
from modules.registry import find_module, get_registry

log = structlog.get_logger()


# ── State ──────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    # Ticket fields (input)
    ticket_id: str
    title: str
    description: str
    labels: list[str]
    reporter: str
    assignee: str
    # Populated during processing
    intent: Optional[dict]
    module_name: Optional[str]
    artifact_content: Optional[str]
    risk_level: Optional[str]
    artifact_explanation: Optional[str]
    # Output
    result: Optional[str]
    error: Optional[str]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _artifact_from_state(state: AgentState) -> Artifact:
    return Artifact(
        content=state["artifact_content"] or "",
        risk_level=state["risk_level"] or "low",  # type: ignore[arg-type]
        explanation=state.get("artifact_explanation") or "",
        module_name=state["module_name"] or "",
    )


# ── Nodes ──────────────────────────────────────────────────────────────────────

def parse_intent_node(state: AgentState) -> dict:
    try:
        intent = parse_intent(state["title"], state["description"], state["labels"])
        return {"intent": intent.model_dump()}
    except Exception as exc:
        log.error("intent_parse_failed", ticket=state["ticket_id"], error=str(exc))
        return {"error": f"Intent parsing failed: {exc}"}


def route_node(state: AgentState) -> dict:
    if state.get("error"):
        return {}
    try:
        intent = ParsedIntent(**state["intent"])
        module = find_module(state["labels"], intent)
        if module is None:
            return {"error": f"No module handles labels {state['labels']}"}
        return {"module_name": module.name}
    except Exception as exc:
        log.error("routing_failed", ticket=state["ticket_id"], error=str(exc))
        return {"error": f"Routing failed: {exc}"}


def generate_node(state: AgentState) -> dict:
    if state.get("error"):
        return {}
    try:
        from modules.base import AgentTask

        intent = ParsedIntent(**state["intent"])
        task = AgentTask(
            ticket_id=state["ticket_id"],
            title=state["title"],
            description=state["description"],
            labels=state["labels"],
            reporter=state["reporter"],
            assignee=state["assignee"],
        )
        module = get_registry()[state["module_name"]]
        artifact = module.generate(task, intent)
        return {
            "artifact_content": artifact.content,
            "risk_level": artifact.risk_level,
            "artifact_explanation": artifact.explanation,
        }
    except Exception as exc:
        log.error("generate_failed", ticket=state["ticket_id"], error=str(exc))
        return {"error": f"Artifact generation failed: {exc}"}


def needs_approval_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Phase 1 stub: posts the artifact with an approval notice, skips execution.
    Phase 3 will implement real polling for /approve comments.
    """
    ticket_id = state["ticket_id"]
    jira_client: JiraClient = config["configurable"]["jira_client"]
    try:
        body = (
            f"*Farman — approval required* \u26a0\ufe0f\n\n"
            f"*Risk level:* `{state['risk_level']}`\n\n"
            f"Proposed artifact:\n"
            f"{{code:yaml}}\n{state['artifact_content']}\n{{code}}\n\n"
            f"_Approval workflow (Phase 3) is not yet implemented. "
            f"Execution has been skipped. Set DRY_RUN_MODE=false and lower "
            f"the risk level, or wait for Phase 3._"
        )
        jira_client.post_comment(ticket_id, body)
    except Exception as exc:
        log.error("needs_approval_comment_failed", ticket=ticket_id, error=str(exc))
    return {"error": "Approval required — execution skipped (Phase 3 feature)"}


def execute_node(state: AgentState) -> dict:
    if state.get("error"):
        return {}
    try:
        if settings.dry_run_mode:
            log.info("dry_run_skip_execute", ticket=state["ticket_id"])
            return {
                "result": (
                    "[DRY RUN] Artifact generated successfully.\n"
                    "Set DRY_RUN_MODE=false in .env to execute for real."
                )
            }

        from modules.base import AgentTask

        task = AgentTask(
            ticket_id=state["ticket_id"],
            title=state["title"],
            description=state["description"],
            labels=state["labels"],
            reporter=state["reporter"],
            assignee=state["assignee"],
        )
        module = get_registry()[state["module_name"]]
        result = module.execute(_artifact_from_state(state), task)
        return {"result": result}
    except Exception as exc:
        log.error("execute_failed", ticket=state["ticket_id"], error=str(exc))
        return {"error": f"Execution failed: {exc}"}


def report_node(state: AgentState, config: RunnableConfig) -> dict:
    ticket_id = state["ticket_id"]
    jira_client: JiraClient = config["configurable"]["jira_client"]
    try:
        if state.get("error"):
            body = (
                f"*Farman* encountered an error processing this ticket:\n\n"
                f"{{code}}\n{state['error']}\n{{code}}\n\n"
                f"Please review and reassign to retry."
            )
            jira_client.post_comment(ticket_id, body)
        else:
            mode_tag = " _(DRY RUN — no changes made)_" if settings.dry_run_mode else ""
            body = (
                f"*Farman* — `{state['module_name']}` artifact ready{mode_tag}\n\n"
                f"*Risk level:* `{state['risk_level']}`\n"
                f"*Summary:* {state.get('artifact_explanation', '')}\n\n"
                f"{{code:yaml}}\n{state['artifact_content']}\n{{code}}\n"
            )
            if state.get("result"):
                body += f"\n*Result:*\n{{code}}\n{state['result']}\n{{code}}"

            jira_client.post_comment(ticket_id, body)
            jira_client.transition_ticket(ticket_id, settings.jira_done_transition)
    except Exception as exc:
        log.error("report_failed", ticket=ticket_id, error=str(exc))
    return {}


# ── Routing conditions ─────────────────────────────────────────────────────────

def _route_after_intent(state: AgentState) -> str:
    return "report" if state.get("error") else "route"


def _route_after_route(state: AgentState) -> str:
    return "report" if state.get("error") else "generate"


def _route_after_generate(state: AgentState) -> str:
    if state.get("error"):
        return "report"
    if requires_approval(state.get("risk_level", "low")):
        return "needs_approval"
    return "execute"


# ── Graph ──────────────────────────────────────────────────────────────────────

def build_graph() -> Any:
    graph = StateGraph(AgentState)

    graph.add_node("parse_intent", parse_intent_node)
    graph.add_node("route", route_node)
    graph.add_node("generate", generate_node)
    graph.add_node("needs_approval", needs_approval_node)
    graph.add_node("execute", execute_node)
    graph.add_node("report", report_node)

    graph.add_edge(START, "parse_intent")
    graph.add_conditional_edges(
        "parse_intent",
        _route_after_intent,
        {"route": "route", "report": "report"},
    )
    graph.add_conditional_edges(
        "route",
        _route_after_route,
        {"generate": "generate", "report": "report"},
    )
    graph.add_conditional_edges(
        "generate",
        _route_after_generate,
        {"execute": "execute", "needs_approval": "needs_approval", "report": "report"},
    )
    graph.add_edge("execute", "report")
    graph.add_edge("needs_approval", "report")
    graph.add_edge("report", END)

    return graph.compile()


_graph: Any = None


def get_graph() -> Any:
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
