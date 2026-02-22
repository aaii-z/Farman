from __future__ import annotations

import os
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

from config.settings import settings


def get_llm() -> BaseChatModel:
    """
    Returns the core language model used by the agent dynamically based on settings.
    This ensures compatibility with any AI provider supported by LangChain 
    (OpenAI, Anthropic, Google, Ollama, etc.).
    """
    # Inject API key into env variables for LangChain to discover if provided
    if settings.llm_api_key:
        if settings.llm_provider == "openai":
            os.environ["OPENAI_API_KEY"] = settings.llm_api_key
        elif settings.llm_provider == "anthropic":
            os.environ["ANTHROPIC_API_KEY"] = settings.llm_api_key
        elif settings.llm_provider == "google_genai":
            os.environ["GOOGLE_API_KEY"] = settings.llm_api_key
        elif settings.llm_provider == "groq":
            os.environ["GROQ_API_KEY"] = settings.llm_api_key

    return init_chat_model(
        model=settings.llm_model,
        model_provider=settings.llm_provider,
        temperature=settings.llm_temperature,
        base_url=settings.llm_base_url,
    )
