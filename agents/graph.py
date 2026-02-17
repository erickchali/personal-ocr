from langgraph.graph import END, START, StateGraph

from agents.graph_state import FinancialAssistantState
from agents.nodes import (
    list_files_node,
    process_files_node,
    query_stub_node,
    respond_node,
    router_node,
)


def route_by_intent(state: FinancialAssistantState) -> str:
    """Route to the appropriate node based on classified intent."""
    intent = state.get("intent", "chat")
    if intent == "upload":
        return "list_files"
    elif intent == "query":
        return "query_stub"
    return "respond"


builder = StateGraph(FinancialAssistantState)

# Add nodes
builder.add_node("router", router_node)
builder.add_node("list_files", list_files_node)
builder.add_node("process_files", process_files_node)
builder.add_node("query_stub", query_stub_node)
builder.add_node("respond", respond_node)

# Edges
builder.add_edge(START, "router")
builder.add_conditional_edges(
    "router",
    route_by_intent,
    {"list_files": "list_files", "query_stub": "query_stub", "respond": "respond"},
)
builder.add_edge("list_files", "process_files")
builder.add_edge("process_files", "respond")
builder.add_edge("query_stub", END)
builder.add_edge("respond", END)

graph = builder.compile()
