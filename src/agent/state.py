"""
Agent state schema for the LangGraph sustainability strategy agent.
"""

from typing import Any, Optional
from typing_extensions import TypedDict


class PortfolioSummaryState(TypedDict, total=False):
    """Subset of portfolio summary fields carried in agent state."""
    total_properties: int
    avg_composite_score: float
    max_composite_score: float
    min_composite_score: float
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    total_expected_annual_loss_usd: float
    top_hazards: dict[str, int]


class AgentState(TypedDict, total=False):
    """
    LangGraph state for the sustainability strategy agent.

    Flows through nodes:
      analyze_risks → retrieve_knowledge → find_incentives
      → calculate_roi → generate_strategy → (refine | report)
    """

    # ---- Input (set at invocation) ----
    risk_scores: list[dict]                     # Stage 1 scored properties
    portfolio_summary: PortfolioSummaryState     # Aggregated stats
    user_query: str                             # Broker request / chat message

    # ---- Working memory (populated by nodes) ----
    identified_risks: list[dict]                # Parsed risk signals per property
    retrieved_context: list[dict]               # RAG chunks
    retrofit_options: list[dict]                # ROI-calculated measures
    incentives: list[dict]                      # Matched incentives
    benchmark_results: list[dict]               # Energy benchmark comparisons

    # ---- Output ----
    recommendations: list[dict]                 # Ranked action items
    strategy_narrative: str                     # LLM-generated strategy text
    total_incentives_usd: float
    total_savings_usd: float
    report_path: Optional[str]                  # Path to generated report
    messages: list[dict]                        # Conversation history [{role, content}]
    error: Optional[str]                        # Error message if any node fails
