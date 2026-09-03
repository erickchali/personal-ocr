from functools import cache
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from config import settings

LLMRole = Literal["default", "extraction", "router", "query", "respond"]

# Fallbacks when no LLM_MODEL_* env var is set. Slugs: https://openrouter.ai/models
DEFAULT_MODELS: dict[str, str] = {
    "default": "google/gemini-2.5-flash",
    # flash over pro: measured on a 70-transaction statement, identical output at ~5x the
    # speed and ~7x cheaper, and pro intermittently returned empty content via OpenRouter.
    "extraction": "google/gemini-2.5-flash",
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

    return settings.model_for_role(role) or DEFAULT_MODELS[role]


@cache
def get_llm(role: LLMRole = "default") -> BaseChatModel:
    """Return the chat model configured for a given role, routed through OpenRouter.

    Cached per role, so changing an LLM_MODEL_* value needs a process restart.
    """
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key from openrouter.ai/keys."
        )

    return init_chat_model(
        resolve_model(role),
        model_provider="openrouter",
        temperature=0,
        # Route only to upstream providers that honour the parameters we send. Without it
        # OpenRouter may pick one that ignores response_format or tool schemas and returns
        # empty content on an otherwise *successful* call — which no retry would catch.
        openrouter_provider={"require_parameters": True},
    )
