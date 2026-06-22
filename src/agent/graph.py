"""
LangGraph state machine for the sustainability strategy agent.

Defines the workflow:
  analyze_risks → retrieve_knowledge → find_incentives
  → calculate_roi → generate_strategy → (refine | report)
"""

import logging
from langgraph.graph import StateGraph, END

from src.agent.state import AgentState
from src.agent import nodes

logger = logging.getLogger(__name__)


def build_strategy_graph() -> StateGraph:
    """
    Build and compile the LangGraph workflow for strategy generation.

    Returns a compiled graph ready for invocation.
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("analyze_risks", nodes.analyze_risks)
    graph.add_node("retrieve_knowledge", nodes.retrieve_knowledge)
    graph.add_node("find_incentives", nodes.find_incentives)
    graph.add_node("calculate_roi", nodes.calculate_roi)
    graph.add_node("generate_strategy", nodes.generate_strategy)
    graph.add_node("generate_report", nodes.generate_report)

    # Define edges (linear pipeline for strategy generation)
    graph.set_entry_point("analyze_risks")
    graph.add_edge("analyze_risks", "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "find_incentives")
    graph.add_edge("find_incentives", "calculate_roi")
    graph.add_edge("calculate_roi", "generate_strategy")
    graph.add_edge("generate_strategy", END)

    compiled = graph.compile()
    logger.info("Strategy generation graph compiled successfully")
    return compiled


def build_report_graph() -> StateGraph:
    """
    Build a minimal graph for report generation from existing strategy data.
    """
    graph = StateGraph(AgentState)
    graph.add_node("generate_report", nodes.generate_report)
    graph.set_entry_point("generate_report")
    graph.add_edge("generate_report", END)

    compiled = graph.compile()
    logger.info("Report generation graph compiled")
    return compiled


def build_chat_graph() -> StateGraph:
    """
    Build a minimal graph for chat refinement.
    """
    graph = StateGraph(AgentState)
    graph.add_node("refine_strategy", nodes.refine_strategy)
    graph.set_entry_point("refine_strategy")
    graph.add_edge("refine_strategy", END)

    compiled = graph.compile()
    logger.info("Chat refinement graph compiled")
    return compiled


# ---------------------------------------------------------------------------
# Convenience: pre-compiled graphs
# ---------------------------------------------------------------------------

_strategy_graph = None
_report_graph = None
_chat_graph = None


def get_strategy_graph():
    """Get or create the strategy generation graph (singleton)."""
    global _strategy_graph
    if _strategy_graph is None:
        _strategy_graph = build_strategy_graph()
    return _strategy_graph


def get_report_graph():
    """Get or create the report generation graph (singleton)."""
    global _report_graph
    if _report_graph is None:
        _report_graph = build_report_graph()
    return _report_graph


def get_chat_graph():
    """Get or create the chat refinement graph (singleton)."""
    global _chat_graph
    if _chat_graph is None:
        _chat_graph = build_chat_graph()
    return _chat_graph
