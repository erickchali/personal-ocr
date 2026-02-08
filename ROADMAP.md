# Financial Assistant Roadmap

Transform the PDF processor into a multi-node LangGraph financial assistant.

---

## Phase 1: Foundation - State & Tools

### 1.1 Create State Schema
**File**: `agents/graph_state.py`

```python
from typing import TypedDict, Optional, Annotated
from langgraph.graph.message import add_messages

class FinancialAssistantState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: Optional[str]  # "upload", "query", "both", "chat"
    pending_files: list[str]
    current_file: Optional[str]
    pdf_content: Optional[str]
    extracted_statement: Optional[dict]
    saved_statement_ids: list[int]
    query_result: Optional[str]
    errors: list[str]
```

**Concepts to learn**:
- `TypedDict` for type hints
- `Annotated` with `add_messages` for automatic message accumulation
- How LangGraph uses state to pass data between nodes

**Resources**:
- https://docs.langchain.com/oss/python/langgraph/overview
- Search: "langgraph state management"

---

### 1.2 Add Query Functions to Database
**File**: `db/cruds.py`

Add these functions to the existing file:

```python
def get_transactions_filtered(
    start_date: str = None,
    end_date: str = None,
    currency: str = None,
    transaction_type: str = None,
    limit: int = 50
) -> list[dict]:
    """Query transactions with optional filters."""
    # TODO: Build dynamic SQL query based on filters
    pass

def get_highest_expense(period_months: int = 6) -> dict:
    """Get the highest expense in given period."""
    # TODO: Query with ORDER BY amount DESC LIMIT 1
    pass

def get_spending_by_category(period_months: int = 1) -> list[dict]:
    """Aggregate spending by transaction_type."""
    # TODO: GROUP BY transaction_type, SUM(amount)
    pass
```

**Concepts to learn**:
- Dynamic SQL query building
- Date filtering in SQLite
- Aggregation queries (GROUP BY, SUM)

---

### 1.3 Create Query Tools
**File**: `agents/tools.py`

```python
from langchain_core.tools import tool
from db.cruds import get_transactions_filtered, get_highest_expense, get_spending_by_category

@tool
def search_transactions(
    start_date: str = None,
    end_date: str = None,
    currency: str = None,
    limit: int = 10
) -> str:
    """Search transactions with filters. Dates in YYYY-MM-DD format."""
    results = get_transactions_filtered(start_date, end_date, currency, limit=limit)
    # Format results as string for LLM
    return str(results)

@tool
def get_top_expense(months: int = 6) -> str:
    """Get the highest expense in the last N months."""
    result = get_highest_expense(months)
    return f"Highest expense: {result['description']} - {result['amount']} {result['currency']}"

@tool
def spending_summary(months: int = 1) -> str:
    """Get spending breakdown by category for last N months."""
    results = get_spending_by_category(months)
    return str(results)
```

**Concepts to learn**:
- `@tool` decorator from langchain
- Tool descriptions (LLM uses these to decide when to call)
- Input/output types for tools

---

## Phase 2: Build Nodes

### 2.1 Create Nodes File
**File**: `agents/nodes.py`

```python
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import PyPDFLoader
from agents.graph_state import FinancialAssistantState
from agents.models import CreditCardStatement
from db.cruds import save_statement, statement_exists
from pathlib import Path

model = ChatOpenAI(model="gpt-4.1", temperature=0)
PDF_DIRECTORY = Path(__file__).parent.parent / "pdf-to-process"


def router_node(state: FinancialAssistantState) -> dict:
    """Classify user intent from the last message."""
    # TODO:
    # 1. Get last user message from state["messages"]
    # 2. Use LLM to classify intent: "upload", "query", "both", "chat"
    # 3. Return {"intent": classified_intent}
    pass


def process_pdf_node(state: FinancialAssistantState) -> dict:
    """Read PDF and extract text content."""
    # TODO:
    # 1. Get current_file or first file from pending_files
    # 2. Use PyPDFLoader to extract text
    # 3. Return {"pdf_content": text, "current_file": filename}
    pass


def extract_data_node(state: FinancialAssistantState) -> dict:
    """Extract structured data from PDF text using LLM."""
    # TODO:
    # 1. Get pdf_content from state
    # 2. Use model.with_structured_output(CreditCardStatement)
    # 3. Return {"extracted_statement": statement.model_dump()}
    pass


def save_to_db_node(state: FinancialAssistantState) -> dict:
    """Save extracted statement to database."""
    # TODO:
    # 1. Get extracted_statement from state
    # 2. Check if exists with statement_exists()
    # 3. Call save_statement() if new
    # 4. Return {"saved_statement_ids": [...]}
    pass


def query_node(state: FinancialAssistantState) -> dict:
    """Answer questions using database tools."""
    # TODO:
    # 1. Create agent with query tools
    # 2. Get user question from messages
    # 3. Run agent and get response
    # 4. Return {"query_result": response}
    pass


def respond_node(state: FinancialAssistantState) -> dict:
    """Generate final response to user."""
    # TODO:
    # 1. Check what was done (upload, query, both)
    # 2. Compose response message
    # 3. Return {"messages": [AIMessage(content=response)]}
    pass
```

**Concepts to learn**:
- Node functions receive state, return state updates
- Each node does ONE thing
- State updates are merged automatically

---

## Phase 3: Build the Graph

### 3.1 Create Graph Definition
**File**: `agents/graph.py`

```python
from langgraph.graph import StateGraph, START, END
from agents.graph_state import FinancialAssistantState
from agents.nodes import (
    router_node,
    process_pdf_node,
    extract_data_node,
    save_to_db_node,
    query_node,
    respond_node,
)


def route_by_intent(state: FinancialAssistantState) -> str:
    """Conditional edge: route based on classified intent."""
    intent = state.get("intent")
    if intent == "upload" or intent == "both":
        return "process_pdf"
    elif intent == "query":
        return "query"
    else:
        return "respond"


def after_save(state: FinancialAssistantState) -> str:
    """After saving, check if we also need to query."""
    if state.get("intent") == "both":
        return "query"
    return "respond"


# Build the graph
builder = StateGraph(FinancialAssistantState)

# Add nodes
builder.add_node("router", router_node)
builder.add_node("process_pdf", process_pdf_node)
builder.add_node("extract_data", extract_data_node)
builder.add_node("save_to_db", save_to_db_node)
builder.add_node("query", query_node)
builder.add_node("respond", respond_node)

# Add edges
builder.add_edge(START, "router")
builder.add_conditional_edges("router", route_by_intent)
builder.add_edge("process_pdf", "extract_data")
builder.add_edge("extract_data", "save_to_db")
builder.add_conditional_edges("save_to_db", after_save)
builder.add_edge("query", "respond")
builder.add_edge("respond", END)

# Compile
graph = builder.compile()


# Optional: Visualize the graph
if __name__ == "__main__":
    print(graph.get_graph().draw_mermaid())
```

**Concepts to learn**:
- `StateGraph` is the main builder
- `add_node(name, function)` registers nodes
- `add_edge(from, to)` creates direct edges
- `add_conditional_edges(from, routing_function)` creates branching
- `compile()` creates the runnable graph

---

### 3.2 Create Entry Point
**File**: `main.py`

```python
from agents.graph import graph
from langchain_core.messages import HumanMessage

def chat(message: str, files: list[str] = None):
    """Send a message to the financial assistant."""
    initial_state = {
        "messages": [HumanMessage(content=message)],
        "pending_files": files or [],
        "saved_statement_ids": [],
        "errors": [],
    }

    result = graph.invoke(initial_state)

    # Get the last AI message
    last_message = result["messages"][-1]
    return last_message.content


if __name__ == "__main__":
    # Test upload
    response = chat(
        "Process my bank statements",
        files=["statement1.pdf", "statement2.pdf"]
    )
    print(response)

    # Test query
    response = chat("What was my highest expense last month?")
    print(response)
```

---

## Phase 4: Testing Checkpoints

### 4.1 Test State Flow
```bash
# Run graph visualization
python -c "from agents.graph import graph; print(graph.get_graph().draw_mermaid())"
```

### 4.2 Test PDF Processing
```bash
python -c "
from agents.graph import graph
from langchain_core.messages import HumanMessage

result = graph.invoke({
    'messages': [HumanMessage(content='Process my statements')],
    'pending_files': ['your-test-file.pdf'],
    'saved_statement_ids': [],
    'errors': [],
})
print(result)
"
```

### 4.3 Test Queries
```bash
python -c "
from agents.graph import graph
from langchain_core.messages import HumanMessage

result = graph.invoke({
    'messages': [HumanMessage(content='What was my highest expense?')],
    'pending_files': [],
    'saved_statement_ids': [],
    'errors': [],
})
print(result['messages'][-1].content)
"
```

---

## Phase 5: Enhancements (Optional)

### 5.1 Add Checkpointing (Persistence)
```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# Now you can resume conversations
result = graph.invoke(state, {"configurable": {"thread_id": "user-123"}})
```

### 5.2 Add Human-in-the-Loop
```python
from langgraph.prebuilt import ToolNode
from langgraph.graph import interrupt

def save_to_db_node(state):
    # Ask for approval before saving
    approval = interrupt("About to save statement. Approve?")
    if approval == "yes":
        # proceed with save
        pass
```

### 5.3 Add Streaming
```python
# Instead of invoke, use stream
for event in graph.stream(state):
    print(event)
```

---

## Quick Reference

### Graph Visualization
```
START → router
           ↓
    ┌──────┼──────┐
    ↓      ↓      ↓
process  query  respond
    ↓             ↓
extract           │
    ↓             │
save_to_db ───────┤
    ↓             ↓
    └────→ respond → END
```

### Key Imports
```python
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
```

### File Order to Implement
1. `agents/graph_state.py` (state schema)
2. `db/cruds.py` (add query functions)
3. `agents/tools.py` (query tools)
4. `agents/nodes.py` (node implementations)
5. `agents/graph.py` (wire everything)
6. `main.py` (test it)

---

## Need Help?

If you get stuck, ask about:
- "How do I implement the router_node?"
- "How do conditional edges work?"
- "How do I test a single node?"
- "How do I debug state flow?"
