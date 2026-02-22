from __future__ import annotations

import sys
import time
from datetime import datetime

import structlog
from sqlmodel import Session, SQLModel, create_engine, select

from config.settings import settings
from core.agent import AgentState, get_graph
from db.models import TicketLog
from integrations.jira import JiraClient, get_live_jira_client

# ── Logging setup ──────────────────────────────────────────────────────────────

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        (
            structlog.dev.ConsoleRenderer()
            if sys.stderr.isatty()
            else structlog.processors.JSONRenderer()
        ),
    ]
)

log = structlog.get_logger()

# ── DB ─────────────────────────────────────────────────────────────────────────

engine = create_engine(settings.database_url, echo=False)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def is_already_processed(ticket_id: str) -> bool:
    with Session(engine) as session:
        entry = session.exec(
            select(TicketLog).where(TicketLog.ticket_id == ticket_id)
        ).first()
        return entry is not None and entry.status in ("done", "error")


def save_log(state: AgentState, status: str) -> None:
    with Session(engine) as session:
        entry = TicketLog(
            ticket_id=state["ticket_id"],
            title=state["title"],
            module_name=state.get("module_name"),
            risk_level=state.get("risk_level"),
            artifact=state.get("artifact_content"),
            result=state.get("result"),
            error=state.get("error"),
            status=status,
            dry_run=settings.dry_run_mode,
            updated_at=datetime.utcnow(),
        )
        session.add(entry)
        session.commit()


# ── Ticket processing ──────────────────────────────────────────────────────────

def process_ticket(task, jira_client: JiraClient) -> None:  # noqa: ANN001
    log.info("ticket_start", ticket_id=task.ticket_id, title=task.title)

    initial: AgentState = {
        "ticket_id": task.ticket_id,
        "title": task.title,
        "description": task.description,
        "labels": task.labels,
        "reporter": task.reporter,
        "assignee": task.assignee,
        "intent": None,
        "module_name": None,
        "artifact_content": None,
        "risk_level": None,
        "artifact_explanation": None,
        "result": None,
        "error": None,
    }

    graph = get_graph()
    final: AgentState = graph.invoke(initial, config={"configurable": {"jira_client": jira_client}})

    status = "error" if final.get("error") else "done"
    save_log(final, status)
    log.info("ticket_done", ticket_id=task.ticket_id, status=status)


# ── Main loop ──────────────────────────────────────────────────────────────────

def run_once(jira_client: JiraClient) -> None:
    try:
        tasks = jira_client.poll_pending_tickets()
        for task in tasks:
            if is_already_processed(task.ticket_id):
                log.debug("ticket_skip_already_processed", ticket_id=task.ticket_id)
                continue
            try:
                process_ticket(task, jira_client)
            except Exception as exc:
                log.error("ticket_unhandled_error", ticket_id=task.ticket_id, error=str(exc))
    except Exception as exc:
        log.error("poll_error", error=str(exc))

def run() -> None:
    log.info(
        "farman_starting",
        dry_run=settings.dry_run_mode,
        model=settings.llm_model,
        poll_interval=settings.jira_poll_interval_seconds,
    )
    init_db()
    
    jira_client = get_live_jira_client()

    while True:
        run_once(jira_client)
        log.debug("sleeping", seconds=settings.jira_poll_interval_seconds)
        time.sleep(settings.jira_poll_interval_seconds)


if __name__ == "__main__":
    run()
