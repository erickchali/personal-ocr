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
| **5** | Human-in-the-loop approval | **Current** |
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

## Phase 6–7: Coming Soon

- **Phase 6**: Replace `invoke()` with `stream()` + set up LangSmith dashboard monitoring
- **Phase 7**: Configure `langgraph.json` for LangGraph Studio local deployment
