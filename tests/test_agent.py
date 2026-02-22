from core.agent import get_graph
from integrations.jira import JiraClient
from modules.base import AgentTask

class FakeJiraClient(JiraClient):
    def __init__(self):
        self.comments = []
        self.transitions = []
        
    def poll_pending_tickets(self):
        return []

    def post_comment(self, ticket_id: str, body: str) -> None:
        self.comments.append((ticket_id, body))

    def transition_ticket(self, ticket_id: str, transition_name: str) -> None:
        self.transitions.append((ticket_id, transition_name))

def test_needs_approval_node():
    from core.agent import needs_approval_node
    
    jira_client = FakeJiraClient()
    state = {
        "ticket_id": "TEST-1",
        "risk_level": "high",
        "artifact_content": "fake yaml"
    }
    config = {"configurable": {"jira_client": jira_client}}
    
    result = needs_approval_node(state, config)
    
    assert "error" in result
    assert "Phase 3" in result["error"]
    assert len(jira_client.comments) == 1
    assert jira_client.comments[0][0] == "TEST-1"
    assert "fake yaml" in jira_client.comments[0][1]

def test_report_node_error():
    from core.agent import report_node
    
    jira_client = FakeJiraClient()
    state = {
        "ticket_id": "TEST-2",
        "error": "Simulated error"
    }
    config = {"configurable": {"jira_client": jira_client}}
    
    report_node(state, config)
    
    assert len(jira_client.comments) == 1
    assert "Simulated error" in jira_client.comments[0][1]

def test_report_node_success():
    from core.agent import report_node
    
    jira_client = FakeJiraClient()
    state = {
        "ticket_id": "TEST-3",
        "error": None,
        "module_name": "ansible",
        "risk_level": "low",
        "artifact_content": "playbook",
        "artifact_explanation": "did nothing",
        "result": "success run"
    }
    config = {"configurable": {"jira_client": jira_client}}
    
    report_node(state, config)
    
    assert len(jira_client.comments) == 1
    assert "ansible" in jira_client.comments[0][1]
    assert "playbook" in jira_client.comments[0][1]
    assert "success run" in jira_client.comments[0][1]
    
    assert len(jira_client.transitions) == 1
    assert jira_client.transitions[0][0] == "TEST-3"
