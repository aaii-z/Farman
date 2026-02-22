from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM Configuration
    llm_provider: str = "openai"  # openai, anthropic, ollama, google_genai, etc.
    llm_model: str = "gpt-4o"
    llm_api_key: str = ""
    llm_temperature: float = 0.0
    llm_base_url: str | None = None  # Useful for local models like Ollama / vLLM

    # Jira
    jira_url: str = ""
    jira_username: str = ""
    jira_api_token: str = ""
    jira_bot_user: str = ""
    jira_poll_interval_seconds: int = 30
    jira_done_transition: str = "Done"
    jira_in_progress_transition: str = "In Progress"

    # Behaviour
    dry_run_mode: bool = True
    approval_timeout_minutes: int = 60
    authorized_approvers: str = ""

    @property
    def authorized_approvers_list(self) -> list[str]:
        if not self.authorized_approvers.strip():
            return []
        return [x.strip() for x in self.authorized_approvers.split(",")]

    # Database
    database_url: str = "sqlite:///farman.db"

settings = Settings()
