# CLAUDE.md — Financial Assistant Learning Project

This file is automatically read by Claude Code when opening this project.
It keeps the learning path and architecture consistent across any machine or collaborator.

---

## What This Project Is

A **learning project** for LangChain, LangGraph, and LangSmith. The app is a financial assistant
chatbot that processes credit card statement PDFs and answers questions about the stored data.

**The goal is learning, not production.** Every architectural decision prioritizes teaching
real-world LangGraph patterns over shipping features fast. When suggesting changes, always
explain the *why* behind them.

---

## How to Work With the Developer

This project follows a specific learning workflow. **Do not skip it.**

1. **Explain first** — Before writing any implementation code, explain what we're building and why.
   Cover: what the concept is, why this approach over alternatives, and what it teaches.
2. **Guide, don't implement** — The developer writes the implementation code. Provide hints,
   signatures, and pointers to existing code to reuse — not complete solutions.
3. **Review on request** — When asked to review code, give specific, actionable feedback.
   Point to exact line numbers. Don't rewrite the code unless asked.
4. **One phase at a time** — Follow the ROADMAP.md phases in order. Don't jump ahead.
5. **Answer the "why"** — If the developer asks why we're doing X instead of Y, always answer.
   This is a learning project — understanding the reasoning is as important as the code.
6. **Ground suggestions in official docs** — When suggesting or explaining LangChain/LangGraph/LangSmith
   code, always check the official documentation first using the `docs-langchain` MCP server
   (`search_docs_by_lang_chain` and `query_docs_filesystem_docs_by_lang_chain`). APIs evolve fast and prebuilts get
   deprecated (e.g., `create_react_agent` → `create_agent`). Cite the relevant doc page so the developer
   can read further. Never rely solely on training data for framework-specific patterns.

---

## Tech Stack

| Tool | Purpose | Version |
|------|---------|---------|
| Python | Language | 3.12+ |
| LangGraph | Graph orchestration (StateGraph, nodes, edges) | >=1.2.11 |
| LangChain | LLM integrations, tools | >=1.3.18 |
| LangSmith | Tracing and monitoring | ==0.7.23 |
| OpenRouter | Single LLM gateway — every model, one key | via langchain-openrouter |
| PostgreSQL | Database (via pgvector/pgvector:pg16 Docker image) | 16 |
| SQLAlchemy | ORM for database models and queries | >=2.0 |
| Alembic | Database migration framework | latest |
| Pydantic | Data validation and structured LLM output | >=2.12.5 |
| uv | Package manager and task runner | latest |
| Ruff | Linting and formatting | >=0.15.1 |

---

## Project Structure

```
personal-ocr/
├── agents/
│   ├── extraction.py       # LLM-based PDF data extraction (structured output)
│   ├── graph.py            # StateGraph definition — exposes builder + compiled graph
│   ├── graph_state.py      # FinancialAssistantState TypedDict
│   ├── llm.py              # Per-role LLM factory over OpenRouter (see LLM_MODEL_* env vars)
│   ├── nodes.py            # Node functions: router, query, respond
│   └── pdf_reader_agent.py # LEGACY: original create_agent implementation (keep as reference)
├── domain/
│   └── models.py           # Shared vocabulary: CreditCardStatement, Transaction, etc.
├── db/
│   ├── cruds.py            # Database operations: save, query, check duplicates
│   ├── database.py         # SQLAlchemy engine + session factory (reads DATABASE_URL)
│   ├── models.py           # SQLAlchemy ORM models: StatementModel, TransactionModel
│   └── schemas.py          # Pydantic response schemas for DB layer output
├── alembic/
│   ├── env.py              # Alembic config (reads DATABASE_URL, imports Base metadata)
│   └── versions/           # Auto-generated migration scripts
├── pdf-to-process/         # Drop PDF bank statements here for processing
├── .github/workflows/
│   └── lint.yml            # CI: ruff check + format on PRs to main
├── .env                    # API keys (never commit this)
├── .env.example            # Template for .env
├── CLAUDE.md               # This file
├── ROADMAP.md              # Phase-by-phase implementation plan
├── langgraph.json          # LangGraph Studio graph registration
├── main.py                 # CLI entry point
└── pyproject.toml          # Dependencies + ruff config
```

---

## Key Architecture Decisions

### Why StateGraph instead of create_agent?
`create_agent` (used in `pdf_reader_agent.py`) is a high-level abstraction that hides the graph.
`StateGraph` exposes explicit nodes, edges, and state — giving full control and visibility.
The old agent is kept as a reference to compare both approaches.

### Why nodes for PDF processing, tools for queries?
- **Nodes** are used when the flow is deterministic (always list → process → respond)
- **Tools** are used when the LLM needs to decide what to do (query intent varies per question)
The query path uses `query_node` + `ToolNode` + `tools_condition` to form an agentic loop where the LLM picks which tool(s) to call.

### Why expose both `builder` and a compiled `graph`?
`agents/graph.py` exports the uncompiled `builder` AND a `graph` compiled without a checkpointer.
- `langgraph dev` uses the compiled `graph` (Studio provides its own persistence)
- `main.py` imports `builder` and compiles its own version with `InMemorySaver` for CLI memory
This avoids the "custom checkpointer conflicts with platform" error from LangGraph Studio.

### Why TypedDict for state, not Pydantic?
LangGraph merges partial state updates from each node. TypedDict supports this natively.
Pydantic models are immutable by default, which makes merging harder.

### Why Ruff instead of black + flake8?
One tool for linting, formatting, and import sorting. 10-100x faster. Industry standard in 2025+.

### Why OpenRouter instead of per-provider SDKs?
The old factory dispatched on *vendor* (`LLM_PROVIDER=google|openai|anthropic`), so every model
change meant a different Python class, a different package, and a different API key. OpenRouter
speaks one API in front of every vendor, which collapses that axis: a model becomes a plain string
like `google/gemini-2.5-pro` that lives in `.env`.

That unlocks the real win — **models are chosen per role, not globally**. `agents/llm.py` maps a
role (`extraction`, `router`, `query`, `respond`, `default`) to a model slug via `LLM_MODEL_<ROLE>`.
The intent router does a trivial 3-way classification and runs on the cheapest tier; the text-to-SQL
node needs the strongest tool-caller available. Before this, one shared `llm` served both.

**Use `ChatOpenRouter` (via `init_chat_model("openrouter:<slug>")`), not `ChatOpenAI` with
`base_url`.** Pointing `ChatOpenAI` at OpenRouter is a common shortcut, and the
[docs warn against it](https://docs.langchain.com/oss/python/langchain/models#base-url-and-proxy-settings):
`ChatOpenAI` targets the OpenAI spec only, so it silently drops non-standard response fields
(`reasoning`, `reasoning_details`) and OpenRouter routing metadata. It also breaks
[model profiles](https://docs.langchain.com/oss/python/langchain/models#model-profiles), which
`create_agent` reads to auto-pick `ProviderStrategy` vs `ToolStrategy` for structured output.

### Why PostgreSQL?
Started on SQLite for zero-config learning, moved to Postgres in Phase 8 to teach real migration
and connection patterns (Alembic, a read-only role for the SQL agent, pgvector available for future
semantic search). Runs via the `pgvector/pgvector:pg16` Docker image.

### All functions that return data must have a Pydantic response schema
Never return raw dicts from functions. Define a Pydantic model in the appropriate schemas file
(e.g., `db/schemas.py`) and use it as the return type. Use `model_validate()` with
`from_attributes=True` to convert ORM models to Pydantic. This ensures type safety, serialization
consistency, and a clear contract between layers.

---

## Common Commands

```bash
# Run the chatbot
uv run python main.py

# Lint check
uv run ruff check .

# Format check (what CI runs)
uv run ruff format --check .

# Auto-fix formatting
uv run ruff format .

# Auto-fix lint issues
uv run ruff check --fix .

# Visualize the graph (Mermaid)
uv run python -c "from agents.graph import graph; print(graph.get_graph().draw_mermaid())"

# Run LangGraph Studio locally
uv run langgraph dev

# Start Docker services (Postgres, MinIO, Metabase)
docker compose up -d

# Run database migrations
uv run alembic upgrade head

# Generate a new migration after changing db/models.py
uv run alembic revision --autogenerate -m "describe the change"
```

---

## Environment Setup

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required keys:
- `LANGSMITH_API_KEY` — for tracing (get from smith.langchain.com)
- `LANGSMITH_TRACING=true`
- `LANGSMITH_PROJECT=learning-path`
- `OPENROUTER_API_KEY` — the only LLM key needed (get from openrouter.ai/keys)

Optional — pick the model per scenario. Each takes an OpenRouter model slug and falls back to
`LLM_MODEL_DEFAULT`, then to the built-in default in `agents/llm.py`:
- `LLM_MODEL_DEFAULT`, `LLM_MODEL_EXTRACTION`, `LLM_MODEL_ROUTER`, `LLM_MODEL_QUERY`, `LLM_MODEL_RESPOND`

Install dependencies:
```bash
uv sync
```

---

## Roadmap Status

See `ROADMAP.md` for the detailed phase-by-phase plan.

| Phase | Focus | Status  |
|-------|-------|---------|
| 0 | CI/CD: Ruff + GitHub Actions | Done    |
| 1 | StateGraph skeleton + intent router | Done    |
| 2 | Wire PDF processing into graph nodes | Done    |
| 3 | Query tools for financial data | Done    |
| 4 | Checkpointing + multi-turn conversation | Done    |
| 5 | Human-in-the-loop approval | Done    |
| 6 | Streaming + LangSmith monitoring | Done    |
| 7 | LangGraph Studio + LangSmith tracing | Done    |
| 8 | Postgres + SQLAlchemy + Alembic + SQL Agent | Done    |
| 8.5 | OpenRouter gateway + per-role model selection | Done    |
| 9 | Split ingestion out of the graph | Done    |
| 10 | Ingestion pipeline: MinIO + hash-based idempotency | Pending |
| 11 | FastAPI: uploads, statements, metrics | Pending |
| 12 | Next.js app on Agent Chat UI (`useStream`) | Pending |
| 13 | (Optional) Metabase connected to Postgres | Pending |

---

## LangGraph Studio

Two graphs are registered in `langgraph.json`:
- `financial_assistant` — the new StateGraph (active development)
- `pdf_reader_agent` — the legacy create_agent implementation (reference only)

Run `uv run langgraph dev` to open both in LangGraph Studio.
