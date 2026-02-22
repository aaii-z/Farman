from __future__ import annotations

import abc
import structlog
from functools import lru_cache

from jira import JIRA
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from modules.base import AgentTask

log = structlog.get_logger()

# All labels that signal Farman should pick up a ticket
TRIGGER_LABELS = {"ansible", "terraform", "k8s", "kubernetes", "argocd"}


class JiraClient(abc.ABC):
    @abc.abstractmethod
    def poll_pending_tickets(self) -> list[AgentTask]:
        ...

    @abc.abstractmethod
    def post_comment(self, ticket_id: str, body: str) -> None:
        ...

    @abc.abstractmethod
    def transition_ticket(self, ticket_id: str, transition_name: str) -> None:
        ...


class LiveJiraClient(JiraClient):
    def __init__(self) -> None:
        self.jira = JIRA(
            server=settings.jira_url,
            basic_auth=(settings.jira_username, settings.jira_api_token),
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def poll_pending_tickets(self) -> list[AgentTask]:
        label_filter = " OR ".join(f'labels = "{lbl}"' for lbl in TRIGGER_LABELS)
        jql = (
            f'assignee = "{settings.jira_bot_user}" '
            f'AND status = "To Do" '
            f'AND ({label_filter})'
        )
        issues = self.jira.search_issues(
            jql,
            maxResults=20,
            fields="summary,description,labels,reporter,assignee",
        )
        tasks = []
        for issue in issues:
            f = issue.fields
            tasks.append(
                AgentTask(
                    ticket_id=issue.key,
                    title=f.summary,
                    description=f.description or "",
                    labels=list(f.labels),
                    reporter=f.reporter.accountId if f.reporter else "",
                    assignee=f.assignee.accountId if f.assignee else "",
                )
            )
        log.info("jira_poll_complete", ticket_count=len(tasks))
        return tasks

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def post_comment(self, ticket_id: str, body: str) -> None:
        self.jira.add_comment(ticket_id, body)
        log.info("comment_posted", ticket_id=ticket_id)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def transition_ticket(self, ticket_id: str, transition_name: str) -> None:
        available = self.jira.transitions(ticket_id)
        for t in available:
            if t["name"].lower() == transition_name.lower():
                self.jira.transition_issue(ticket_id, t["id"])
                log.info("ticket_transitioned", ticket_id=ticket_id, to=transition_name)
                return
        log.warning("transition_not_found", ticket_id=ticket_id, wanted=transition_name)


@lru_cache(maxsize=1)
def get_live_jira_client() -> JiraClient:
    return LiveJiraClient()
