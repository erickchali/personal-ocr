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

---

## Tech Stack

| Tool | Purpose | Version |
|------|---------|---------|
| Python | Language | 3.12+ |
| LangGraph | Graph orchestration (StateGraph, nodes, edges) | >=1.0.3 |
| LangChain | LLM integrations, tools | >=1.1.3 |
| LangSmith | Tracing and monitoring | >=0.4.43 |
| Google Gemini | Default LLM (gemini-2.5-flash) | via langchain-google-genai |
| SQLite | Database for statements and transactions | built-in |
| Pydantic | Data validation and structured LLM output | >=2.12.5 |
| uv | Package manager and task runner | latest |
| Ruff | Linting and formatting | >=0.15.1 |

---

## Project Structure

```
langchain-learning/
├── agents/
│   ├── extraction.py       # LLM-based PDF data extraction (structured output)
│   ├── graph.py            # StateGraph definition — nodes, edges, compilation
│   ├── graph_state.py      # FinancialAssistantState TypedDict
│   ├── llm.py              # Configurable LLM factory (Google/OpenAI/Anthropic)
│   ├── models.py           # Pydantic models: CreditCardStatement, Transaction, etc.
│   ├── nodes.py            # Node functions: router, list_files, process_files, respond
│   └── pdf_reader_agent.py # LEGACY: original create_agent implementation (keep as reference)
├── db/
│   ├── cruds.py            # Database operations: save, query, check duplicates
│   └── init_db.py          # SQLite schema initialization
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
Phase 3 will introduce tools for the query path.

### Why TypedDict for state, not Pydantic?
LangGraph merges partial state updates from each node. TypedDict supports this natively.
Pydantic models are immutable by default, which makes merging harder.

### Why Ruff instead of black + flake8?
One tool for linting, formatting, and import sorting. 10-100x faster. Industry standard in 2025+.

### Why SQLite?
Simple, zero-config, file-based. Good for learning DB patterns without infrastructure setup.
Phase 3+ could evolve to PostgreSQL or add a vector DB for semantic search.

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

# Initialize the database manually
uv run python -m db.init_db
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
- One of: `GOOGLE_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`
- `LLM_PROVIDER=google` (or `openai` or `anthropic`)

Install dependencies:
```bash
uv sync
```

---

## Roadmap Status

See `ROADMAP.md` for the detailed phase-by-phase plan.

| Phase | Focus | Status |
|-------|-------|--------|
| 0 | CI/CD: Ruff + GitHub Actions | Done |
| 1 | StateGraph skeleton + intent router | Done |
| 2 | Wire PDF processing into graph nodes | In Progress |
| 3 | Query tools for financial data | Pending |
| 4 | Checkpointing + multi-turn conversation | Pending |
| 5 | Human-in-the-loop approval | Pending |
| 6 | Streaming + LangSmith monitoring | Pending |
| 7 | LangGraph Studio + deployment | Pending |

---

## LangGraph Studio

Two graphs are registered in `langgraph.json`:
- `financial_assistant` — the new StateGraph (active development)
- `pdf_reader_agent` — the legacy create_agent implementation (reference only)

Run `uv run langgraph dev` to open both in LangGraph Studio.
