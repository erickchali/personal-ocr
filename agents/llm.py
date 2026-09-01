import os
from functools import cache
from typing import Literal

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

load_dotenv()

LLMRole = Literal["default", "extraction", "router", "query", "respond"]

# Fallbacks when no LLM_MODEL_* env var is set. Slugs: https://openrouter.ai/models
DEFAULT_MODELS: dict[str, str] = {
    "default": "google/gemini-2.5-flash",
    "extraction": "google/gemini-2.5-pro",
    "router": "google/gemini-2.5-flash-lite",
    "query": "anthropic/claude-sonnet-4.5",
    "respond": "google/gemini-2.5-flash",
}


def resolve_model(role: LLMRole = "default") -> str:
    """Resolve the OpenRouter model slug for a role.

    Order: LLM_MODEL_<ROLE> -> LLM_MODEL_DEFAULT -> DEFAULT_MODELS[role].

    Separate from get_llm() so the model choice can be tested without an API key.
    """
    if role not in DEFAULT_MODELS:
        raise ValueError(f"Unknown LLM role {role!r}. Expected one of {sorted(DEFAULT_MODELS)}.")

    return os.getenv(f"LLM_MODEL_{role.upper()}") or os.getenv("LLM_MODEL_DEFAULT") or DEFAULT_MODELS[role]


@cache
def get_llm(role: LLMRole = "default") -> BaseChatModel:
    """Return the chat model configured for a given role, routed through OpenRouter.

    Cached per role, so changing an LLM_MODEL_* value needs a process restart.
    """
    if not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key from openrouter.ai/keys."
        )

    return init_chat_model(
        resolve_model(role),
        model_provider="openrouter",
        temperature=0,
    )
