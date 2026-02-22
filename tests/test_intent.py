from __future__ import annotations

from core.intent import parse_intent
from modules.base import ParsedIntent
from langchain_core.runnables import RunnableLambda

def test_parse_intent(mocker):
    # Mock the LLM factory
    mock_llm_class = mocker.patch("core.intent.get_llm")
    
    # Create a fake runable that will replace with_structured_output
    expected_intent = ParsedIntent(
        action="install",
        target="nginx",
        environment="dev",
        hosts=["all"],
        parameters={"version": "1.20"}
    )
    
    def mock_with_structured_output(*args, **kwargs):
        # We ignore the prompt when invoked and just return the expected intent
        return RunnableLambda(lambda prompt_val: expected_intent)
        
    mock_llm_class.return_value.with_structured_output = mock_with_structured_output
    
    result = parse_intent("Install nginx", "Put it on web-1 in prod", ["ansible"])
    
    assert result.action == "install"
    assert result.target == "nginx"
    assert result.environment == "dev"
    assert result.parameters["version"] == "1.20"
