from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agents.graph_state import FinancialAssistantState
from agents.nodes import (
    list_files_node,
    process_files_node,
    query_node,
    respond_node,
    router_node,
)
from agents.tools import (
    fetch_all_statements,
    fetch_statement_transactions,
)


def route_by_intent(state: FinancialAssistantState) -> str:
    """Route to the appropriate node based on classified intent."""
    intent = state.get("intent", "chat")
    if intent == "upload":
        return "list_files"
    elif intent == "query":
        return "query"
    return "respond"


builder = StateGraph(FinancialAssistantState)

# Add nodes
builder.add_node("router", router_node)
builder.add_node("list_files", list_files_node)
builder.add_node("process_files", process_files_node)
builder.add_node("tools", ToolNode([fetch_statement_transactions, fetch_all_statements]))
builder.add_node("query", query_node)
builder.add_node("respond", respond_node)

# Edges
builder.add_edge(START, "router")
builder.add_conditional_edges(
    "router",
    route_by_intent,
    {"list_files": "list_files", "query": "query", "respond": "respond"},
)
builder.add_conditional_edges("query", tools_condition, {"tools": "tools", END: END})
builder.add_edge("list_files", "process_files")
builder.add_edge("process_files", "respond")
builder.add_edge("tools", "query")
builder.add_edge("respond", END)

graph = builder.compile()
