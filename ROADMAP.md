# Financial Assistant — Roadmap

Transform the PDF processor into a multi-node LangGraph financial assistant chatbot.

---

## How We Work Together

1. **I explain** — What we're building, why, and the key concepts
2. **You write the code** — Using this plan as your guide
3. **You ask when stuck** — I'll guide you, not just give you the answer
4. **I review** — Once you have it working, I suggest improvements
5. **We verify** — Run the verification steps together

---

## Full Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| **0** | CI/CD: Ruff linting + GitHub Actions | Done |
| **1** | StateGraph skeleton + intent router | Done |
| **2** | Wire PDF processing into graph nodes | Done |
| **3** | Add query tools for financial data | Done |
| **4** | Checkpointing + multi-turn conversation | Done |
| **5** | Human-in-the-loop approval | Done |
| **6** | Streaming + LangSmith monitoring | Done |
| **7** | LangGraph Studio + LangSmith tracing | Done |
| **8** | Postgres + SQLAlchemy + Alembic + SQL Agent | Done |
| **8.5** | OpenRouter gateway + per-role model selection | Done |
| **9** | Split ingestion out of the graph | Done |
| **10** | Ingestion pipeline: MinIO + hash-based idempotency | Done |
| **11** | FastAPI: uploads, statements, metrics | Done |
| **12** | Evaluation: datasets + reconciliation evaluators | Pending |
| **13** | Model fallbacks for provider faults | Pending |
| **14** | Persistent checkpointer (PostgresSaver) | Pending |
| **15** | Semantic search over transactions (pgvector) | Pending |
| **16** | Long-term memory across threads (Store) | Pending |
| **17** | Prompt management in LangSmith | Pending |
| **18** | Next.js app on Agent Chat UI (`useStream`) | Pending |
| **19** | (Optional) Metabase connected to Postgres | Pending |

---

## Phase 0: CI/CD — Done

- Ruff linting/formatting configured in `pyproject.toml`
- GitHub Actions workflow at `.github/workflows/lint.yml` (runs on PRs to main)

## Phase 1: StateGraph Skeleton — Done

- `agents/graph_state.py` — `FinancialAssistantState` with messages + intent
- `agents/llm.py` — Per-role LLM factory over OpenRouter (`LLM_MODEL_<ROLE>` env vars)
- `agents/nodes.py` — Router node with structured output, stub nodes, respond node
- `agents/graph.py` — StateGraph with conditional edges routing by intent
- `main.py` — Interactive CLI chat loop

---

## Phase 2: Wire PDF Processing Into Graph Nodes — Done

Replaced the `upload_stub_node` with a multi-step PDF processing flow:

```
router --("upload")--> list_files --> process_files --> respond --> END
```

- `agents/nodes.py` — `list_files_node` scans `pdf-to-process/`, `process_files_node` extracts and saves to DB
- `agents/extraction.py` — Standalone `extract_structured_data()` using `llm.with_structured_output(CreditCardStatement)`
- `agents/graph_state.py` — Added `pending_files` and `processed_count` fields
- Each node communicates through state, not direct calls

---

## Phase 3: Query Tools for Financial Data — Done

Replaced `query_stub_node` with the first **agentic loop** in the graph. The LLM now decides which tool to call based on the user's question.

### What was built

- `agents/tools.py` — Two `@tool`-decorated functions that wrap the existing CRUD layer:
  - `fetch_all_statements()` — lists all stored statements
  - `fetch_statement_transactions(statement_id)` — fetches one statement with its transactions
- `agents/nodes.py` — `query_node` binds the tools to the LLM with `llm.bind_tools([...])` and invokes it
- `agents/graph.py` — Added a `ToolNode` and a conditional edge with `tools_condition`

### The agentic loop

```
router --("query")--> query --> tools_condition
                        ^             |
                        |             v
                       tools     tools or END
```

If the LLM emits tool calls, `tools_condition` routes to `ToolNode` which executes them, then loops back to `query`. If the LLM is done, it routes to `END`.

### Concepts practiced

- **`@tool` decorator** — exposing Python functions to the LLM with type hints + docstrings
- **`bind_tools()`** — giving the LLM a "menu" of tools to choose from (returns a new LLM instance)
- **`ToolNode`** — prebuilt node that auto-executes tool calls and returns `ToolMessage`s
- **`tools_condition`** — prebuilt conditional edge that routes based on whether the LLM emitted tool calls
- **The agentic loop** — LLM decides → tool runs → LLM sees result → LLM decides again → ... → done

---

## Phase 4: Checkpointing & Multi-turn Conversation — Done

Without checkpointing, every `graph.invoke()` started from scratch. Now the graph remembers context across turns within the same session.

### What was built

- `agents/graph.py` — Exposes the `builder` (uncompiled) and a `graph` compiled without a checkpointer (so `langgraph dev` can attach its own)
- `main.py` — Imports the `builder`, compiles its own graph **once at startup** with `InMemorySaver`, and passes a `thread_id` in the config on every invoke

### Key insight: builder vs compiled graph

The graph **definition** (nodes, edges) is shared. The **compilation** is environment-specific:
- `langgraph dev` (Studio) — server provides its own persistence, so we compile without a checkpointer
- `main.py` (CLI) — compiles with `InMemorySaver` for in-process memory

### Verification

```
You: Show me all my statements
Assistant: [calls fetch_all_statements, lists them]
You: Tell me more about the first one
Assistant: [resolves "the first one" from message history, calls fetch_statement_transactions]
```

### Concepts practiced

- **Checkpointers** save graph state at every super-step, keyed by `thread_id`
- **Threads** = conversations; same `thread_id` = same memory
- **`configurable.thread_id`** is the special config key LangGraph looks for
- **Compile once, at startup** — never inside a request loop
- **In-process vs persistent checkpointers** — `InMemorySaver` for dev, `SqliteSaver`/`PostgresSaver` for production

---

## Phase 5: Human-in-the-Loop Approval — Done                                                       
                  
  Split the old `process_files_node` into a multi-step flow with a human checkpoint:                  
   
  list_files --> extract_files --> approval (interrupt) --approve--> save_files --> respond --> END   
                                                        --reject--> cancel --> END
                                                                                                      
### What was built
                                                                                                      
- `agents/nodes.py` — Split `process_files_node` into three new nodes:
  - `extract_files_node` — PDF parsing + LLM extraction, stores results in `pending_statements`     
  - `approval_node` — calls `interrupt()` to pause and surface a summary, then routes via           
`Command(goto=...)`                                                                                 
  - `save_files_node` — writes approved statements to the DB                                        
  - `cancel_node` — returns a static rejection message (avoids LLM hallucination on the rejection   
path)                                                                                               
- `agents/graph_state.py` — Added `pending_statements: list[CreditCardStatement]` field
- `agents/graph.py` — Rewired edges for the new extract → approval → save/cancel flow               
- `main.py` — Detects `__interrupt__` in the result, prompts the user, resumes with                 
`Command(resume=bool)`                                                                              
                                                                                                      
### Key design decisions                                                                            
                  
- **Dedicated `cancel_node`** instead of routing rejections through `respond_node` — the LLM would  
hallucinate confused responses because the rejection wasn't in message history
- **`Command(goto=...)`** for dynamic routing from inside the approval node — requires              
`Literal[...]` type annotation on the return type                                                   
- **Expensive work before `interrupt()`** — extraction happens in the upstream node so it doesn't
re-run on resume                                                                                    
                  
### Concepts practiced                                                                              
                  
- **`interrupt()`** — pauses the graph and surfaces a payload to the caller                         
- **`Command(resume=...)`** — sends the human's decision back; becomes the return value of
`interrupt()`                                                                                       
- **`Command(goto=...)`** — dynamic node routing from inside a node (vs conditional edges)
- **Why checkpointing is foundational** — without Phase 4, there's no saved state to resume from    
- **Code before `interrupt()` re-runs on resume** — design accordingly

---

## Phase 6: Streaming + LangSmith Monitoring — Done

Replaced `graph.invoke()` with `graph.stream()` for real-time output and added custom progress updates.

### What was built

- `main.py` — Replaced `invoke()` with `stream()` using v2 format and multiple stream modes (`"updates"` + `"custom"`). Handles interrupt detection and resume within the streaming loop.
- `agents/nodes.py` — Added `get_stream_writer()` to `extract_files_node` to emit per-file progress updates during PDF processing.
- LangSmith traces verified at smith.langchain.com — node execution, LLM calls, tool calls all visible.

### Key concepts

- **`graph.stream()`** — yields chunks as the graph executes, instead of blocking until completion
- **Stream modes** — `"updates"` (node state updates), `"custom"` (user-defined progress), `"messages"` (LLM tokens), `"values"` (full state snapshots)
- **`version="v2"`** — recommended format (requires LangGraph >= 1.1), chunks are dicts with `type`/`data` keys
- **`get_stream_writer()`** — emit custom status messages from inside nodes (side-channel, not saved in state or LangSmith)
- **`@traceable`** — LangSmith decorator to trace custom functions (not needed here since LangGraph auto-traces nodes and LLM calls)

### Concepts practiced

- **Streaming vs invoke** — trade-offs between simplicity and real-time UX
- **Multiple stream modes** — combining node updates with custom progress in a single loop
- **LangSmith observability** — reading traces to debug node execution, LLM inputs/outputs, and tool calls

---

## Phase 7: LangGraph Studio + LangSmith — Done

- `langgraph.json` registers both graphs — `financial_assistant` (the StateGraph) and
  `pdf_reader_agent` (the legacy `create_agent` reference) — and declares `"env": ".env"`.
- `agents/graph.py` exports an uncompiled `builder` **and** a `graph` compiled without a
  checkpointer, so Studio can attach its own persistence while `main.py` compiles with
  `InMemorySaver`. Avoids the "custom checkpointer conflicts with platform" error.
- `uv run langgraph dev` serves both graphs with thread state in `.langgraph_api/`.
- `.vscode/launch.json` runs the dev server under the debugger. Reload is on, so the code runs
  in a child process — `"subProcess": true` is what binds breakpoints there.
- LangSmith tracing is live via `LANGSMITH_*` in `.env`; traces land in the `learning-path` project.

### Gotcha

Cost attribution in LangSmith is derived by matching `ls_provider` + `ls_model_name` against its
pricing table. Since Phase 8.5 that pair is `openrouter` + a slug like `anthropic/claude-sonnet-4.5`,
which may not resolve — traces and token counts stay correct, but cost can read $0 until model
prices are added under LangSmith's Model pricing settings.

---

## Phase 8: Postgres + SQLAlchemy + Alembic + SQL Agent — Done

Replaced SQLite with PostgreSQL, added ORM models, migrations, Pydantic response schemas, tests, and an LLM-powered SQL agent.

### What was built

- **Docker infrastructure** — `docker-compose.yml` with Postgres (pgvector), MinIO, Metabase. All host ports parametrized via `.env`.
- **SQLAlchemy ORM** — `db/models.py` with `StatementModel` and `TransactionModel` replacing raw SQL.
- **Alembic migrations** — `alembic/` directory with auto-generated migrations. Schema changes are version-controlled.
- **Pydantic response schemas** — `db/schemas.py` defines the contract between the DB layer and the rest of the app (`StatementDetailResponse`, `StatementListItem`, etc.).
- **Rewritten CRUDs** — `db/cruds.py` uses SQLAlchemy queries and returns Pydantic models instead of raw dicts.
- **SQL Agent** — `SQLDatabaseToolkit` gives the LLM tools to inspect schema and write SQL queries from natural language.
- **Read-only DB user** — `query_reader` Postgres user with only SELECT privileges for the SQL agent. Auto-created via Docker init script.
- **System prompt** — `query_node` includes a system message instructing the LLM to only generate SELECT queries.
- **Tests** — `tests/test_cruds.py` with 14 tests using a throwaway SQLite DB. CI updated to run tests.
- **Date columns** — Migrated from `String` to proper `Date` type for all date fields.

### Key design decisions

- **Three schema layers** — `agents/models.py` (LLM extraction), `db/models.py` (ORM/DB), `db/schemas.py` (response contracts). Each serves a different purpose.
- **Defense in depth for SQL safety** — system prompt (soft) + read-only DB user (hard). Security enforced at database level, not application level.
- **`SQLDatabaseToolkit`** over custom tools — battle-tested, includes schema inspection and query checking out of the box.
- **SQLite for tests, Postgres for app** — tests don't need Docker, CI stays simple.

### Concepts practiced

- **SQLAlchemy 2.x** — `DeclarativeBase`, `Mapped[]`, `mapped_column()`, `model_validate(from_attributes=True)`
- **Alembic** — `revision --autogenerate`, `upgrade head`, `postgresql_using` for type migrations
- **Text-to-SQL** — LLM inspects schema and writes queries to answer natural language questions
- **Layered security** — system prompts + database-level access control

---

## Phase 8.5: OpenRouter — Done

- `agents/llm.py` — factory now dispatches on **role**, not vendor. `resolve_model(role)` reads
  `LLM_MODEL_<ROLE>` → `LLM_MODEL_DEFAULT` → built-in default; `get_llm(role)` builds it via
  `init_chat_model(slug, model_provider="openrouter")`.
- Dropped `langchain-openai`, `-anthropic`, `-google-genai`, `-google-vertexai`. One
  `OPENROUTER_API_KEY` replaces three vendor keys.
- Both entry points migrated: `agents/nodes.py` (three role LLMs) and `agents/pdf_reader_agent.py`.

### Key design decisions

- **`ChatOpenRouter`, not `ChatOpenAI` + `base_url`** — the latter targets the OpenAI spec only and
  silently drops `reasoning` fields, routing metadata, and model profiles.
- **Roles beat providers** — the router classifies 3 ways and runs on the cheapest tier; the SQL node
  needs the strongest tool-caller. One shared `llm` previously served both.
- **Failures are loud** — unknown role raises `ValueError`, missing key raises `RuntimeError`. The
  old factory fell off the end and returned `None`.

---

## Phase 9: Split Ingestion Out of the Graph — Done

The graph conflated a *deterministic pipeline* (ingestion) with an *agentic loop* (Q&A) behind one
LLM intent classifier. Uploading isn't a conversational act — it's an event — so classifying it cost
an LLM call to detect something a function call can just state.

- `agents/graph.py` — removed `list_files`, `extract_files`, `approval`, `cancel`, `save_files`.
  Nine nodes → four: `router → query ⇄ tools → respond`.
- `agents/nodes.py` — deleted the five ingestion nodes and their imports.
- `agents/graph_state.py` — dropped `pending_files`, `pending_statements`, `processed_count`.
- Deleted `agents/legacy_nodes.py` and `agents/tools.py` (both already unreferenced).

### Bugs fixed

- **Query path skipped `respond`** — `tools_condition` mapped `END → END`, so the user saw
  `query_node`'s raw output. Now `{END: "respond"}`.
- **`intent` was an unconstrained `str`** — legal values lived only in the `Field` description, so
  the schema didn't constrain the model. Now `Literal["query", "chat"]`.
- **`idx_transactions_statement_id` indexed the wrong table** — declared on `StatementModel` against
  `"id"`, duplicating that PK. Moved to `TransactionModel` against `statement_id`, the FK actually
  joined on. **Needs a migration** — folded into Phase 10.

### Concepts practiced

- **Pipelines vs agents** — use a graph where the LLM genuinely decides; use plain code where the
  flow is fixed. The router's job shrank from 3 intents to 2.
- **`Literal` in structured output** — constraining the schema beats describing constraints in prose.

---

## Phase 10: Ingestion Pipeline — Done

MinIO finally wired up, and idempotency moved *above* the expensive step.

- `db/models.py` — `object_key`, `file_sha256` (unique), `status` columns
- `api/storage.py` — boto3 over MinIO; content-addressed keys (`statements/<sha256>.pdf`)
- `api/ingestion.py` — `ingest_pdf()`: hash -> store -> parse -> extract -> save
- `db/cruds.py` — `statement_by_hash`, `attach_source`, `approve_statement`, and a
  `try/except IntegrityError` that raises `DuplicateStatementError` instead of dying

### Three rungs, cheapest first

| Check | Catches | Cost |
|---|---|---|
| `file_sha256` | identical file re-uploaded | free |
| `uq_statement` | same statement, different file | one extraction |
| `IntegrityError` handler | two uploads racing | one extraction |

Measured: second upload of the same PDF went from 21.3s to 0.00s.

### Gotcha found while building

When rung two fires, the *existing* row has no hash recorded — so that file would pay for
extraction on every future upload. `attach_source()` teaches the row its hash on the way
out, and never overwrites one already set.

### Concepts practiced

- **Idempotency is about placement** — a check is only cheap if it runs before the
  expensive call. The hash check is what makes a fire-and-forget background task safe.
- **Check-then-act is not atomic** — `statement_exists()` and `save_statement()` use
  separate sessions; only the DB constraint actually guarantees uniqueness.
- **Async HITL** — `interrupt()` needs a human present. A background task has none, so the
  pause becomes durable state: `status='pending'` plus an approve endpoint.

---

## Phase 11: FastAPI — Done

- `api/main.py` — app, CORS for `localhost:3000`, `ensure_bucket()` on lifespan startup
- `api/routers/` — `uploads`, `statements`, `metrics`
- `POST /uploads` returns **202** and queues extraction via `BackgroundTasks`

No chat route: the client streams from `langgraph dev` through `useStream`, which already
handles streaming, threads and interrupts.

### Key design decision

The duplicate check runs **inside** the request while extraction runs after it. One indexed
lookup is cheap enough to do inline, so a repeat upload gets a real answer (11ms, with the
statement id) instead of a hopeful "accepted".

### Concepts practiced

- **202 Accepted** — the right code for "queued, not finished"
- **`BackgroundTasks`** — runs in-process after the response; no broker, but dies with the
  process. Acceptable only because ingestion is idempotent.
- **Portable SQL** — `/metrics` groups months with `extract()` rather than `to_char()`, so
  the same query runs on Postgres and the SQLite test DB.

## Phase 12: Evaluation — Pending

Tracing tells you *what happened*; evaluation tells you whether it was **right**. Extraction is
graded by eye today — flash was chosen over pro on three manual runs and a human reading the output.

- **Dataset** — the real statements in `pdf-to-process/`, which already cover two bank formats
- **Reconciliation evaluators** — no labelling required, because the document asserts its own
  arithmetic:
  - `previous_balance + purchases - payments ≈ current_balance`
  - `sum(transactions where type='purchase') ≈ purchases_gtq`
  - `sum(transactions where type='payment') ≈ payments_gtq`
- **Experiments** — change a model or prompt, re-run, compare scores side by side
- **CI quality gate** — fail the build when extraction accuracy regresses

Use **deterministic code evaluators, not LLM-as-judge**: for extraction the correct answer is
knowable, so scoring it with another model only adds noise and cost. Dropping a transaction or
misreading an amount breaks the totals — which is how the negative-amount bug would have been
caught automatically.

Docs: [quickstart](https://docs.langchain.com/langsmith/evaluation-quickstart),
[custom code evaluators](https://docs.langchain.com/langsmith/bind-evaluator-to-dataset#custom-code-evaluators),
[quality gate](https://docs.langchain.com/langsmith/read-local-experiment-results#implement-a-quality-gate).

---

## Phase 13: Model Fallbacks — Pending

`.with_fallbacks()` so extraction fails over to a different model when a provider misbehaves.
`agents/extraction.py` currently retries the **same** model, which does nothing for a provider-level
fault like the empty responses seen from `gemini-2.5-pro` (see README Notes).

Phase 12 is what proves the chain actually helps rather than assuming it.

---

## Phase 14: Persistent Checkpointer — Pending

`main.py` compiles with `InMemorySaver`, so every conversation dies on restart. Swap in
`PostgresSaver` (`langgraph-checkpoint-postgres`) against the database already running.

Pulls psycopg v3 alongside the existing `psycopg2-binary` — they coexist, don't try to unify them.
Phase 18 wants this anyway for persistent chat threads.

---

## Phase 15: Semantic Search Over Transactions — Pending

`pgvector/pgvector:pg16` has been running since Phase 8 with zero embeddings stored.

SQL cannot answer *"how much do I spend on food delivery?"* — merchants arrive as `PEDIDOSYA GT`,
`UBER EATS`, `MCDONALDS 123`, and no `LIKE` pattern generalises. Embedding the descriptions and
searching by similarity does.

- Embedding column on `transactions`, populated during ingestion
- A retriever tool alongside the SQL toolkit
- The LLM picks: **structured questions → SQL, fuzzy questions → vectors**

---

## Phase 16: Long-term Memory — Pending

Checkpointers remember a *thread*. LangGraph's `BaseStore` remembers across threads — roughly the
difference between a query tool and an assistant.

Examples worth storing: "categorise PEDIDOSYA as groceries", a preferred display currency,
subscriptions the user has already identified as recurring.

---

## Phase 17: Prompt Management — Pending

`agents/extraction.py` holds a hardcoded prompt tuned to one bank's layout — and a second bank
(Promerica) already needed different handling. Moving prompts into LangSmith gives versioning and
makes the prompt a *variable* in Phase 12's experiments, rather than an edit you make and hope about.

---

## Phase 18: Next.js App — Pending

`npx create-agent-chat-app`, chat via `useStream` against `langgraph dev` on :2024, plus `/upload`
and `/dashboard` routes hitting FastAPI. Stretch: generative UI via `push_ui_message`.

## Phase 19: Metabase — Optional

Connect it to the app's Postgres via the `query_reader` role (host `postgres:5432` from inside the
compose network).
