from pydantic import BaseModel
from typing import Dict, Any, List, Optional


class RiskScoreRequest(BaseModel):
    address: str


class SubScores(BaseModel):
    flood: float
    heat: float
    wildfire: float
    transition: float
    seismic: float
    elevation: float


class RiskScoreResponse(BaseModel):
    address: str
    latitude: float
    longitude: float
    composite_score: float
    expected_annual_loss_usd: float
    sub_scores: SubScores
    shap_explanations: Dict[str, float]
    raw_features: Dict[str, Any]


# ---------------------------------------------------------------------------
# Batch / portfolio scoring models
# ---------------------------------------------------------------------------


class BatchRiskScoreRequest(BaseModel):
    """Request body for scoring multiple properties at once."""

    addresses: List[str]


class PortfolioSummary(BaseModel):
    """Aggregate statistics across all successfully-scored properties."""

    total_properties: int
    avg_composite_score: float
    max_composite_score: float
    min_composite_score: float
    high_risk_count: int       # composite_score ≥ 70
    medium_risk_count: int     # 40 ≤ composite_score < 70
    low_risk_count: int        # composite_score < 40
    total_expected_annual_loss_usd: float
    top_hazards: Dict[str, int]  # hazard name → count of properties where it is the top risk


class BatchErrorItem(BaseModel):
    """Details of a single address that failed scoring."""

    address: str
    error: str


class BatchRiskScoreResponse(BaseModel):
    """Response for batch / CSV scoring."""

    results: List[RiskScoreResponse]
    portfolio_summary: PortfolioSummary
    errors: List[BatchErrorItem]


# ---------------------------------------------------------------------------
# Stage 2: Strategy Agent models
# ---------------------------------------------------------------------------


class StrategyRequest(BaseModel):
    """Request body for generating a sustainability strategy."""

    addresses: List[str]
    user_context: str = ""  # Optional broker notes or specific request


class RecommendationItem(BaseModel):
    """A single recommended action in the strategy."""

    category: str
    action: str
    priority: str  # "quick_win", "medium_term", "capex_heavy"
    affected_properties: List[str]
    estimated_cost_usd: float
    estimated_annual_savings_usd: float
    payback_years: Optional[float] = None
    applicable_incentives: List[str] = []
    rationale: str


class StrategyResponse(BaseModel):
    """Response for strategy generation."""

    recommendations: List[RecommendationItem]
    strategy_narrative: str
    portfolio_summary: PortfolioSummary
    total_incentives_usd: float
    total_savings_usd: float
    risk_details: List[Dict[str, Any]] = []          # Per-property sub-scores for heatmap
    regulations: List[Dict[str, Any]] = []            # Matched regulations for compliance roadmap


class ChatRequest(BaseModel):
    """Request body for chat refinement of strategy."""

    message: str
    conversation_history: List[Dict[str, str]] = []  # [{role, content}]
    strategy_context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    """Response for chat refinement."""

    reply: str
    updated_recommendations: Optional[List[RecommendationItem]] = None


class ReportRequest(BaseModel):
    """Request body for PDF report generation."""

    strategy: Dict[str, Any]
    report_title: str = "ClimateNexus Sustainability Strategy"


class ReportResponse(BaseModel):
    """Response for report generation."""

    report_path: str
    format: str  # "html" or "pdf"

