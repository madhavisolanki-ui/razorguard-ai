"""LangGraph State Graph Definition and Workflow Compilation."""

from langgraph.graph import StateGraph, START, END
from src.agent.state import InvestigationState
from src.agent.tools import InvestigationTools
from src.agent.llm import GeminiLLMClient
from src.agent.nodes import (
    observe_node,
    analyze_node,
    create_investigate_node,
    correlate_node,
    decide_node,
    recommend_node,
    create_explain_node,
)


def create_investigation_graph(
    tools: InvestigationTools,
    llm_client: GeminiLLMClient,
):
    """Compiles the LangGraph StateGraph with all investigation nodes and transitions."""
    workflow = StateGraph(InvestigationState)

    # 1. Register Nodes
    workflow.add_node("observe", observe_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("investigate", create_investigate_node(tools))
    workflow.add_node("correlate", correlate_node)
    workflow.add_node("decide", decide_node)
    workflow.add_node("recommend", recommend_node)
    workflow.add_node("explain", create_explain_node(llm_client))

    # 2. Sequential & Deterministic Edges
    workflow.add_edge(START, "observe")
    workflow.add_edge("observe", "analyze")
    workflow.add_edge("analyze", "investigate")
    workflow.add_edge("investigate", "correlate")
    workflow.add_edge("correlate", "decide")
    workflow.add_edge("decide", "recommend")
    workflow.add_edge("recommend", "explain")
    workflow.add_edge("explain", END)

    return workflow.compile()
