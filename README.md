# personal-ocr

A personal finance assistant that ingests credit card statement PDFs and answers questions
about the data. Built as a learning project for LangChain, LangGraph and LangSmith.

- **Architecture and conventions** — [CLAUDE.md](CLAUDE.md)
- **Phase-by-phase plan and history** — [ROADMAP.md](ROADMAP.md)

## Quick start

```bash
cp .env.example .env          # add OPENROUTER_API_KEY (openrouter.ai/keys)
uv sync
docker compose up -d          # postgres, minio, metabase
uv run alembic upgrade head
```

## Running it

| | Command | |
|---|---|---|
| API | `uv run uvicorn api.main:app --reload` | uploads, statements, metrics — `/docs` for Swagger |
| Chat (CLI) | `uv run python main.py` | asks questions against stored data |
| Chat (Studio) | `uv run langgraph dev` | same graph, with tracing UI |
| Evals | `uv run python -m evals.extraction` | scores extraction against anonymised fixtures |

In VS Code, press F5 — [.vscode/launch.json](.vscode/launch.json) has all three, plus a
compound that starts the API and LangGraph server together.

Upload a statement:

```bash
curl -X POST http://localhost:8000/uploads -F "file=@path/to/statement.pdf"
```

Extraction runs in the background; the statement lands as `pending` and needs approval:

```bash
curl -s "localhost:8000/statements?status=pending"
curl -s -X POST localhost:8000/statements/<id>/approve
```

## How ingestion works

```
sha256 ── already stored? ──► return                      (free)
             │ no
             ▼
          MinIO ──► PyPDF ──► LLM extract ──► Postgres
                                                │
                              IntegrityError ──► already stored
```

Three layers of idempotency, cheapest first. The `file_sha256` check runs *before*
extraction, so re-uploading the same PDF costs nothing. `uq_statement`
(card + cut-off date) catches the same statement arriving as a different file.

---

## Notes

Things learned the hard way, kept here so they aren't rediscovered.

### Extraction: flash beats pro

Measured on a 70-transaction statement, `gemini-2.5-flash` vs `gemini-2.5-pro`:

| | pro | flash |
|---|---|---|
| reliability | intermittent empty responses | 3/3 |
| time | 152–165s | 26–40s |
| cost | $0.160 | $0.021 |
| output | 70 transactions | identical |

Pro spent 7,000–13,000 tokens per call on *reasoning*. For a mechanical "read this table
into JSON" task that budget bought nothing, and appeared to correlate with the empty
responses. Flash used zero reasoning tokens.

### OpenRouter can silently drop your parameters

A request asking for `response_format: json_schema` may be routed to an upstream provider
that ignores it. You get a **successful** call with empty content, billed as normal — no
exception, so retry-on-error never fires. Symptom is a confusing
`JSONDecodeError: Expecting value: line 1 column 1` from the output parser.

Two mitigations, both in place:
- `openrouter_provider={"require_parameters": True}` in [agents/llm.py](agents/llm.py)
  restricts routing to providers that support what was sent. It narrows the problem but
  has not eliminated it.
- [agents/extraction.py](agents/extraction.py) uses `include_raw=True` so a bad response
  is inspectable rather than thrown, and retries once.

### Banks disagree about signs

Promerica writes payments as negative (`PAGO, GRACIAS  -15,000.00`); other issuers write
every row positive. `Transaction.amount` is `gt=0` with direction carried by
`transaction_type`, so [domain/models.py](domain/models.py) strips the sign in a
`BeforeValidator` rather than rejecting the statement.

Note this belongs on the **Pydantic** model, not the SQLAlchemy one — by the time data
reaches `db/models.py` it has already been validated, and `@field_validator` is inert on
an ORM class anyway (SQLAlchemy uses `@validates`).

### Prompt instructions leak across bank layouts

A hardcoded `SUB TOTAL XXXXXX NNNN` rule written for one issuer silently corrupted the
*summary* on two others — the model applied a "find numbers near card identifiers" lens to
a bare column of figures. Scoping it (`applies only to transaction rows`) and gating it
(`ONLY IF the statement contains such rows`) took the eval suite from 2/4 to 3/4.

`02-bac-visa` is still red: BAC prints summary values with their labels 20 lines later, and
every prompt variant that fixes it also removes card grouping elsewhere. Tracked in
ROADMAP Phase 12.

### Evaluators are code you wrote, so they can be wrong

`abs(a - b < 0.01)` puts the comparison inside `abs()`, returning `int` rather than `bool`.
LangSmith renders a bool as pass/fail but an int as a score — so a statement off by Q4,020
showed up green. If a board suddenly goes all-green, check the evaluator before celebrating.

### Debugging the servers

Both `uvicorn --reload` and `langgraph dev` serve from a **child** process that watchfiles
respawns on every save. `"subProcess": true` is what lets breakpoints bind there. After a
save, the process you were paused in is gone, so breakpoints can behave erratically — add
`--no-reload` when that gets confusing.

### Ports are configured twice

`POSTGRES_HOST_PORT` and the port inside `DATABASE_URL` used to be set independently, which
is how they drifted apart. [config/settings.py](config/settings.py) now composes the URLs
from the parts, so the port has one source of truth.
