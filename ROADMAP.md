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
| **2** | Wire PDF processing into graph nodes | **Current** |
| **3** | Add query tools for financial data | Pending |
| **4** | Checkpointing + multi-turn conversation | Pending |
| **5** | Human-in-the-loop approval | Pending |
| **6** | Streaming + LangSmith monitoring | Pending |
| **7** | (Stretch) LangGraph Studio + deployment | Pending |

---

## Phase 0: CI/CD — Done

- Ruff linting/formatting configured in `pyproject.toml`
- GitHub Actions workflow at `.github/workflows/lint.yml` (runs on PRs to main)

## Phase 1: StateGraph Skeleton — Done

- `agents/graph_state.py` — `FinancialAssistantState` with messages + intent
- `agents/llm.py` — Configurable LLM factory (Google/OpenAI/Anthropic)
- `agents/nodes.py` — Router node with structured output, stub nodes, respond node
- `agents/graph.py` — StateGraph with conditional edges routing by intent
- `main.py` — Interactive CLI chat loop

---

## Phase 2: Wire PDF Processing Into Graph Nodes (CURRENT)

### What we're building

Replace the `upload_stub_node` with a real multi-step PDF processing flow using **3 new nodes** that each do one thing:

```
router --("upload")--> list_files --> process_files --> respond --> END
```

1. **list_files_node** — Scans the `pdf-to-process/` directory and puts filenames into state
2. **process_files_node** — For each file: reads PDF, extracts structured data with LLM, saves to DB
3. **respond** — (already exists) Generates a summary response for the user

### Why 3 nodes instead of 1 big node?

- **Separation of concerns**: Each node does ONE job. In production, this lets you retry or replace individual steps.
- **LangSmith visibility**: Each node appears as a separate span in traces. With one big node, you'd see one blob. With 3 nodes, you can see exactly where time is spent or where errors happen.
- **State as communication**: Nodes don't call each other directly — they communicate through state. `list_files_node` puts filenames in state, `process_files_node` reads them from state. This is the core LangGraph pattern.

### Why NOT make each file its own separate graph iteration?

For now, we process all files in one `process_files_node` call using a loop. This is simpler and matches what your existing `read_pdf_content` tool already does. In a real production app you might use a [Send API](https://docs.langchain.com/oss/python/langgraph/graph-api) to process files in parallel — but that's an optimization, not a learning priority right now.

### State changes

Your current `FinancialAssistantState` only has `messages` and `intent`. You need to add fields for the PDF processing flow to pass data between nodes.

**File**: `agents/graph_state.py`

Add these fields to `FinancialAssistantState`:
- `pending_files` — list of filenames found in the directory (set by `list_files_node`, read by `process_files_node`)
- `processed_count` — integer tracking how many files were saved to DB (set by `process_files_node`, read by `respond` for the summary)

Think about: what types should these be? Do they need default values? Look at how `intent` is defined for the pattern.

### New nodes

**File**: `agents/nodes.py`

#### `list_files_node(state) -> dict`

**What it does**: Scans the `pdf-to-process/` directory for `.pdf` files and returns their names.

- Use `pathlib.Path` and `.glob("*.pdf")` — you already have this pattern in `pdf_reader_agent.py:57`
- Return a state update with the list of filenames in `pending_files`
- Also return an `AIMessage` telling the user how many files were found (e.g., "Found 2 PDF files to process.")
- Handle edge case: what if the directory is empty or doesn't exist?

#### `process_files_node(state) -> dict`

**What it does**: Reads each PDF, extracts structured data with the LLM, and saves to the database.

This is where you **reuse your existing code** from `pdf_reader_agent.py`. The logic already exists — you're just moving it into a node function.

- Read `pending_files` from state
- For each file:
  - Load PDF with `PyPDFLoader` (see `pdf_reader_agent.py:106-112`)
  - Call a structured extraction function using `llm.with_structured_output(CreditCardStatement)` (see `pdf_reader_agent.py:172-223`)
  - Check for duplicates with `statement_exists()` and save with `save_statement()` (see `pdf_reader_agent.py:124-132`)
- Return state update with `processed_count` and an `AIMessage` summarizing what was processed
- Handle errors gracefully — if one file fails, continue with the rest

**Key decision — where does `extract_structured_data` live?**
Your existing extraction function is in `pdf_reader_agent.py:172`. You have two choices:
1. Move it to `nodes.py` — keeps everything together but makes the file longer
2. Keep it as a utility function in a separate file (e.g., `agents/extraction.py`) — cleaner separation

Either works. Pick whichever makes more sense to you.

### Graph changes

**File**: `agents/graph.py`

- Replace `upload_stub` node with the new `list_files` and `process_files` nodes
- Wire the edges: `router --("upload")--> list_files --> process_files --> respond --> END`
- Remove the `upload_stub_node` import
- The `query_stub` and `respond` paths stay the same

The updated graph should look like:
```
START --> router
            |
    ┌───────┼──────────┐
    v       v          v
list_files  query_stub respond --> END
    |       |
    v       v
process_files  END
    |
    v
  respond --> END
```

### Files to modify

| File | What to change |
|------|---------------|
| `agents/graph_state.py` | Add `pending_files` and `processed_count` to state |
| `agents/nodes.py` | Add `list_files_node` and `process_files_node`, remove `upload_stub_node` |
| `agents/graph.py` | Replace upload_stub with new nodes, update edges |

### Existing code to reuse

All of this logic already exists in `pdf_reader_agent.py` — you're refactoring it into graph nodes:

| What | Where it is now | Where it goes |
|------|----------------|---------------|
| List PDF files | `pdf_reader_agent.py:52-63` | `list_files_node` |
| Load PDF with PyPDFLoader | `pdf_reader_agent.py:106-112` | `process_files_node` |
| Extract structured data | `pdf_reader_agent.py:172-223` | `process_files_node` (or utility) |
| Save to DB + duplicate check | `pdf_reader_agent.py:124-132` | `process_files_node` |
| Extraction prompt | `pdf_reader_agent.py:191-218` | Move with the extraction function |

### Verification

1. `uv run python main.py` then type "Process my statements"
   - Should find PDFs, extract data, save to DB, and respond with a summary
2. Run it again — should detect duplicates and skip them
3. Check LangSmith dashboard — you should see 4 separate node spans: `router → list_files → process_files → respond`
4. `uv run ruff check .` — make sure linting still passes

### Concepts you'll practice

- **Expanding state**: Adding new fields to `TypedDict` as the graph grows
- **Node-to-node communication via state**: `list_files` writes `pending_files`, `process_files` reads it
- **Refactoring existing code into nodes**: Taking working code and restructuring it — a common real-world task
- **Sequential node flow**: `list_files → process_files → respond` is a linear pipeline within the graph

---

## Phase 3–7: Coming Soon

Detailed plans will be written when we get there. High-level:

- **Phase 3**: Add `@tool`-decorated query functions so the chatbot can answer questions about stored data (replaces `query_stub`)
- **Phase 4**: Add `InMemorySaver` checkpointer for multi-turn conversations with `thread_id`
- **Phase 5**: Add `interrupt()` for human approval before saving to DB
- **Phase 6**: Replace `invoke()` with `stream()` + set up LangSmith dashboard monitoring
- **Phase 7**: Configure `langgraph.json` for LangGraph Studio local deployment
