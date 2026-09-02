from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agents.graph_state import FinancialAssistantState
from agents.nodes import query_node, respond_node, router_node, sql_tools


def route_by_intent(state: FinancialAssistantState) -> str:
    """Route to the appropriate node based on classified intent."""
    if state.get("intent") == "query":
        return "query"
    return "respond"


builder = StateGraph(FinancialAssistantState)

# Add nodes
builder.add_node("router", router_node)
builder.add_node("query", query_node)
builder.add_node("tools", ToolNode(sql_tools))
builder.add_node("respond", respond_node)

# Edges
builder.add_edge(START, "router")
builder.add_conditional_edges(
    "router",
    route_by_intent,
    {"query": "query", "respond": "respond"},
)
# Once the LLM stops emitting tool calls, fall through to respond instead of END —
# otherwise query_node's raw tool-shaped output is what the user sees.
builder.add_conditional_edges("query", tools_condition, {"tools": "tools", END: "respond"})
builder.add_edge("tools", "query")
builder.add_edge("respond", END)

graph = builder.compile()
