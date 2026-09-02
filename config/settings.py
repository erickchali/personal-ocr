"""Centralised configuration.

The single place the environment is read. Import `settings` instead of calling
`os.getenv()`, so every variable has one declared name, type, and default.

WHY load_dotenv() IS STILL HERE
Third-party SDKs read os.environ directly and never see this object: the LangSmith
client wants LANGSMITH_API_KEY / LANGSMITH_TRACING, and langchain-openrouter reads
OPENROUTER_APP_TITLE / OPENROUTER_APP_URL. pydantic-settings parses .env without
exporting it, so dropping this call would silently disable tracing. One call, here,
instead of five scattered across the codebase.
"""

from dotenv import load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- OpenRouter ---------------------------------------------------------
    # Deliberately not required: CI and the test suite import this module but never
    # make a model call. agents.llm.get_llm() raises when a call is actually attempted.
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_APP_TITLE: str = "financial-assistant"
    OPENROUTER_APP_URL: str = ""

    # Per-role model slugs. Empty means "fall back to LLM_MODEL_DEFAULT, then to the
    # built-in default in agents/llm.py".
    LLM_MODEL_DEFAULT: str = ""
    LLM_MODEL_EXTRACTION: str = ""
    LLM_MODEL_ROUTER: str = ""
    LLM_MODEL_QUERY: str = ""
    LLM_MODEL_RESPOND: str = ""

    # --- Postgres -----------------------------------------------------------
    POSTGRES_USER: str = "financial_assistant"
    POSTGRES_PASSWORD: str = "financial_assistant_pw"
    POSTGRES_DB: str = "financial_assistant"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_HOST_PORT: int = 5432
    # Read-only role the SQL agent connects as (see docker/postgres/init-read-only-user.sql)
    POSTGRES_READ_USER: str = "query_reader"
    POSTGRES_READ_PASSWORD: str = "query_reader_pw"
    # Set explicitly to override; otherwise composed from the parts above.
    DATABASE_URL: str = ""
    DATABASE_READ_URL: str = ""

    # --- MinIO / object storage ---------------------------------------------
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "minioadmin"
    MINIO_API_HOST_PORT: int = 9000
    MINIO_ENDPOINT_URL: str = ""
    STATEMENTS_BUCKET: str = "statements"

    @model_validator(mode="after")
    def _compose_urls(self) -> "Settings":
        """Build connection URLs from parts when not given explicitly.

        Keeps POSTGRES_HOST_PORT as the single source of truth for the port — the two
        used to be specified independently, which is how DATABASE_URL ended up pointing
        at 5432 while the container published 35432.
        """
        host, port, db = self.POSTGRES_HOST, self.POSTGRES_HOST_PORT, self.POSTGRES_DB

        if not self.DATABASE_URL:
            self.DATABASE_URL = f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{host}:{port}/{db}"
        if not self.DATABASE_READ_URL:
            self.DATABASE_READ_URL = (
                f"postgresql://{self.POSTGRES_READ_USER}:{self.POSTGRES_READ_PASSWORD}@{host}:{port}/{db}"
            )
        if not self.MINIO_ENDPOINT_URL:
            self.MINIO_ENDPOINT_URL = f"http://localhost:{self.MINIO_API_HOST_PORT}"
        return self

    def model_for_role(self, role: str) -> str:
        """LLM_MODEL_<ROLE>, falling back to LLM_MODEL_DEFAULT. Empty if neither is set."""
        return getattr(self, f"LLM_MODEL_{role.upper()}", "") or self.LLM_MODEL_DEFAULT


settings = Settings()
