from dotenv import load_dotenv
load_dotenv()  # Load .env before anything reads os.environ

import asyncio
import csv
import io
import logging
from contextlib import asynccontextmanager
from statistics import mean as _mean

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from src.api.models import (
    RiskScoreRequest,
    RiskScoreResponse,
    SubScores,
    BatchRiskScoreRequest,
    BatchRiskScoreResponse,
    BatchErrorItem,
    PortfolioSummary,
    StrategyRequest,
    StrategyResponse,
    RecommendationItem,
    ChatRequest,
    ChatResponse,
    ReportRequest,
    ReportResponse,
)
from src.ingestion.fema_client import FemaClient
from src.ingestion.noaa_client import NoaaClient
from src.ingestion.wildfire_client import WildfireClient
from src.ingestion.transition_client import TransitionClient
from src.ingestion.usgs_elevation_client import UsgsElevationClient
from src.ingestion.osm_client import OsmClient
from src.ingestion.epa_energy_star_client import EpaEnergyStarClient
from src.ingestion.usgs_seismic_client import UsgsSeismicClient
from src.db.feature_store import FeatureStore
from src.ml.xgboost_ensemble import XGBoostEnsemble
from src.ml.explainer import SHAPExplainer

logger = logging.getLogger(__name__)

# ---------- Geocoding (async-safe) ----------

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


async def geocode_address(address: str) -> tuple[float, float]:
    """
    Geocode an address using the Nominatim API (async, non-blocking).
    Returns (latitude, longitude).
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            NOMINATIM_URL,
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "ClimateNexus-Hackathon/1.0 (climatenexus@jll.com)"},
        )
        resp.raise_for_status()
        results = resp.json()

    if not results:
        raise ValueError(f"No geocoding result for: {address}")

    return float(results[0]["lat"]), float(results[0]["lon"])


# ---------- Shared services ----------

feature_store = FeatureStore()
ml_model = XGBoostEnsemble()
explainer = SHAPExplainer(ml_model)


# ---------- Application Lifespan ----------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hook — init RAG knowledge base."""
    logger.info("ClimateNexus API starting up")

    # Initialize RAG knowledge base (idempotent)
    try:
        from src.rag.vector_store import VectorStore
        from src.rag.knowledge_loader import KnowledgeLoader

        vs = VectorStore()
        if vs.count() == 0:
            loader = KnowledgeLoader(vs)
            n = loader.load_all()
            logger.info("Loaded %d knowledge chunks into vector store", n)
        else:
            logger.info("Vector store already has %d documents", vs.count())
    except Exception as exc:
        logger.warning("RAG initialization failed (non-fatal): %s", exc)

    yield
    logger.info("ClimateNexus API shutting down")


app = FastAPI(
    title="ClimateNexus: Risk Scoring + Strategy Agent API",
    description=(
        "Multi-hazard climate risk scoring engine (Stage 1) with "
        "RAG-powered sustainability strategy agent (Stage 2). "
        "Uses real data from FEMA, NOAA, USFS, USGS, OpenStreetMap, "
        "EPA ENERGY STAR, and a curated sustainability knowledge base."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# =====================================================================
# Helper: create / close a full set of ingestion clients
# =====================================================================


def _create_clients() -> dict:
    return {
        "fema": FemaClient(),
        "noaa": NoaaClient(),
        "wildfire": WildfireClient(),
        "transition": TransitionClient(),
        "elevation": UsgsElevationClient(),
        "osm": OsmClient(),
        "epa": EpaEnergyStarClient(),
        "seismic": UsgsSeismicClient(),
    }


async def _close_clients(clients: dict) -> None:
    await asyncio.gather(*(c.close() for c in clients.values()))


# =====================================================================
# Core scoring logic (shared between single & batch endpoints)
# =====================================================================


async def _score_single_address(
    address: str,
    clients: dict,
) -> RiskScoreResponse:
    """
    Score one property.  Uses the supplied *clients* dict so that
    batch callers can share connections across many addresses.

    Raises ValueError / httpx.HTTPError on geocoding failure.
    """

    # 1. Geocode
    lat, lon = await geocode_address(address)

    # 2. Check cache (avoid re-fetching if already scored)
    cached = feature_store.get_property_features(address)
    if cached is not None:
        features = cached
        logger.info("Cache hit for '%s' – skipping API calls", address)
    else:
        # 3. Parallel data ingestion from 8 real APIs
        (
            fema_res,
            noaa_res,
            wild_res,
            trans_res,
            elev_res,
            osm_res,
            seismic_res,
        ) = await asyncio.gather(
            clients["fema"].get_flood_risk(lat, lon),
            clients["noaa"].get_heat_risk(lat, lon),
            clients["wildfire"].get_wildfire_risk(lat, lon),
            clients["transition"].get_transition_risk(lat, lon, address),
            clients["elevation"].get_elevation(lat, lon),
            clients["osm"].get_building_info(lat, lon),
            clients["seismic"].get_seismic_risk(lat, lon),
        )

        # EPA lookup depends on OSM building type (sequential)
        building_type = osm_res.get("building_type") or "office"
        epa_res = await clients["epa"].get_energy_benchmark(lat, lon, building_type)

        # 4. Merge all features
        features = {
            **fema_res,
            **noaa_res,
            **wild_res,
            **trans_res,
            **elev_res,
            **osm_res,
            **epa_res,
            **seismic_res,
        }

        # 5. Persist to SQLite cache
        feature_store.save_property_features(address, lat, lon, features)

    # 6. ML inference
    prediction = ml_model.predict(features)

    # 7. Explainability
    shap_vals = explainer.explain(features, prediction["composite_score"])

    return RiskScoreResponse(
        address=address,
        latitude=lat,
        longitude=lon,
        composite_score=prediction["composite_score"],
        expected_annual_loss_usd=prediction["eal_usd"],
        sub_scores=SubScores(**prediction["sub_scores"]),
        shap_explanations=shap_vals,
        raw_features=features,
    )


# =====================================================================
# Portfolio summary helper
# =====================================================================


def _compute_portfolio_summary(
    results: list[RiskScoreResponse],
) -> PortfolioSummary:
    """Aggregate scored properties into a portfolio-level summary."""
    if not results:
        return PortfolioSummary(
            total_properties=0,
            avg_composite_score=0,
            max_composite_score=0,
            min_composite_score=0,
            high_risk_count=0,
            medium_risk_count=0,
            low_risk_count=0,
            total_expected_annual_loss_usd=0,
            top_hazards={},
        )

    scores = [r.composite_score for r in results]
    high = sum(1 for s in scores if s >= 70)
    low = sum(1 for s in scores if s < 40)
    medium = len(scores) - high - low

    # Determine which hazard is the *top driver* for each property
    hazard_counts: dict[str, int] = {
        "flood": 0,
        "heat": 0,
        "wildfire": 0,
        "transition": 0,
        "seismic": 0,
    }
    for r in results:
        sub = r.sub_scores
        top_hazard, _ = max(
            [
                ("flood", sub.flood),
                ("heat", sub.heat),
                ("wildfire", sub.wildfire),
                ("transition", sub.transition),
                ("seismic", sub.seismic),
            ],
            key=lambda pair: pair[1],
        )
        hazard_counts[top_hazard] += 1

    return PortfolioSummary(
        total_properties=len(results),
        avg_composite_score=round(_mean(scores), 1),
        max_composite_score=max(scores),
        min_composite_score=min(scores),
        high_risk_count=high,
        medium_risk_count=medium,
        low_risk_count=low,
        total_expected_annual_loss_usd=sum(
            r.expected_annual_loss_usd for r in results
        ),
        top_hazards=hazard_counts,
    )


# =====================================================================
# Internal batch runner (shared by JSON batch & CSV upload endpoints)
# =====================================================================

# Max concurrent property scorings (prevents API rate-limit storms)
_BATCH_CONCURRENCY = 5


async def _run_batch(addresses: list[str]) -> BatchRiskScoreResponse:
    """Score a list of addresses with bounded concurrency."""
    semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)
    results: list[RiskScoreResponse] = []
    errors: list[BatchErrorItem] = []
    lock = asyncio.Lock()

    clients = _create_clients()

    async def _score_one(addr: str) -> None:
        async with semaphore:
            try:
                result = await _score_single_address(addr, clients)
                async with lock:
                    results.append(result)
            except Exception as exc:
                logger.warning("Batch scoring failed for '%s': %s", addr, exc)
                async with lock:
                    errors.append(BatchErrorItem(address=addr, error=str(exc)))

    try:
        await asyncio.gather(*(_score_one(a) for a in addresses))
    finally:
        await _close_clients(clients)

    summary = _compute_portfolio_summary(results)
    return BatchRiskScoreResponse(
        results=results,
        portfolio_summary=summary,
        errors=errors,
    )


# =====================================================================
# Endpoints
# =====================================================================


@app.post("/score", response_model=RiskScoreResponse)
async def score_property(request: RiskScoreRequest):
    """
    Score a single property for multi-hazard climate risk.

    Accepts an address string, geocodes it, fetches real data from 8 public
    APIs in parallel, runs the ML scoring engine, and returns an explainable
    composite risk score (0-100).
    """
    clients = _create_clients()
    try:
        return await _score_single_address(request.address, clients)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"External service error: {exc}"
        )
    finally:
        await _close_clients(clients)


@app.post("/score/batch", response_model=BatchRiskScoreResponse)
async def score_batch(request: BatchRiskScoreRequest):
    """
    Score multiple properties in one request.

    Accepts a JSON list of address strings and returns per-property risk
    scores plus a portfolio-level summary.  Properties are scored with
    bounded concurrency to respect external API rate limits.

    Individual failures are collected in the ``errors`` list — they do not
    abort the entire batch.
    """
    if not request.addresses:
        raise HTTPException(status_code=400, detail="addresses list is empty")
    if len(request.addresses) > 200:
        raise HTTPException(
            status_code=400,
            detail="Batch limited to 200 addresses per request",
        )

    return await _run_batch(request.addresses)


@app.post("/score/upload-csv", response_model=BatchRiskScoreResponse)
async def score_csv(file: UploadFile = File(...)):
    """
    Score a portfolio of properties uploaded as a CSV file.

    The CSV must contain an ``address`` column (case-insensitive).
    Returns per-property risk scores plus a portfolio-level summary.
    """
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))

    addresses: list[str] = []
    for row in reader:
        # Accept common header variants
        addr = (
            row.get("address")
            or row.get("Address")
            or row.get("ADDRESS")
            or row.get("property_address")
            or row.get("Property Address")
        )
        if addr and addr.strip():
            addresses.append(addr.strip())

    if not addresses:
        raise HTTPException(
            status_code=400,
            detail=(
                "No 'address' column found in CSV.  "
                "Expected a column named 'address', 'Address', or 'ADDRESS'."
            ),
        )

    if len(addresses) > 200:
        raise HTTPException(
            status_code=400,
            detail=f"CSV contains {len(addresses)} addresses; max is 200",
        )

    return await _run_batch(addresses)


# =====================================================================
# Stage 2: Strategy Agent Endpoints
# =====================================================================


@app.post("/agent/strategize", response_model=StrategyResponse)
async def generate_strategy(request: StrategyRequest):
    """
    Generate a sustainability strategy for a set of properties.

    Scores the properties (or uses cached scores), then runs the
    LangGraph agent to produce ranked recommendations with ROI,
    incentive matching, and a narrative strategy.
    """
    if not request.addresses:
        raise HTTPException(status_code=400, detail="addresses list is empty")
    if len(request.addresses) > 50:
        raise HTTPException(
            status_code=400,
            detail="Strategy generation limited to 50 addresses",
        )

    # Step 1: Score all properties (reuses Stage 1 batch scoring)
    batch_result = await _run_batch(request.addresses)

    # Step 2: Convert scored results to dicts for the agent
    risk_score_dicts = []
    for r in batch_result.results:
        risk_score_dicts.append({
            "address": r.address,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "composite_score": r.composite_score,
            "expected_annual_loss_usd": r.expected_annual_loss_usd,
            "sub_scores": r.sub_scores.model_dump(),
            "raw_features": r.raw_features,
        })

    portfolio_dict = batch_result.portfolio_summary.model_dump()

    # Step 3: Run the LangGraph agent
    from src.agent.graph import get_strategy_graph

    graph = get_strategy_graph()
    agent_state = {
        "risk_scores": risk_score_dicts,
        "portfolio_summary": portfolio_dict,
        "user_query": request.user_context,
        "messages": [],
    }

    result = graph.invoke(agent_state)

    # Step 4: Build response
    recommendations = [
        RecommendationItem(**rec)
        for rec in result.get("recommendations", [])
    ]

    # Build risk_details for heatmap (per-property sub-scores)
    risk_details = [
        {
            "address": r.address,
            "composite_score": r.composite_score,
            "sub_scores": r.sub_scores.model_dump(),
        }
        for r in batch_result.results
    ]

    # Extract regulation data from the agent result
    from src.agent.nodes import _build_regulation_data
    identified_risks = result.get("identified_risks", [])
    regulations = _build_regulation_data(identified_risks)

    return StrategyResponse(
        recommendations=recommendations,
        strategy_narrative=result.get("strategy_narrative", ""),
        portfolio_summary=batch_result.portfolio_summary,
        total_incentives_usd=result.get("total_incentives_usd", 0),
        total_savings_usd=result.get("total_savings_usd", 0),
        risk_details=risk_details,
        regulations=regulations,
    )


@app.post("/agent/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest):
    """
    Chat refinement — broker asks follow-up questions or requests
    changes to the strategy. Stateless: conversation history and
    strategy context are passed in the request body.
    """
    from src.agent.graph import get_chat_graph

    graph = get_chat_graph()

    # Extract strategy context if provided
    recommendations = []
    strategy_narrative = ""
    if request.strategy_context:
        recommendations = request.strategy_context.get("recommendations", [])
        strategy_narrative = request.strategy_context.get("strategy_narrative", "")

    agent_state = {
        "user_query": request.message,
        "messages": request.conversation_history,
        "recommendations": recommendations,
        "strategy_narrative": strategy_narrative,
    }

    result = graph.invoke(agent_state)

    return ChatResponse(
        reply=result.get("strategy_narrative", ""),
        updated_recommendations=None,
    )


@app.post("/agent/report")
async def generate_report(request: ReportRequest):
    """
    Generate a PDF/HTML report from a finalized strategy.

    Attempts PDF via WeasyPrint first, falls back to HTML.
    Returns the report file as a download.
    """
    from src.agent.tools.report_generator import ReportGenerator

    gen = ReportGenerator()

    try:
        # Try PDF first (WeasyPrint), fall back to HTML
        try:
            path = gen.save_pdf(request.strategy, title=request.report_title)
            media_type = "application/pdf" if path.endswith(".pdf") else "text/html"
        except Exception as pdf_exc:
            logger.warning("PDF generation failed (%s), falling back to HTML", pdf_exc)
            path = gen.save_html(request.strategy, title=request.report_title)
            media_type = "text/html"

        return FileResponse(
            path,
            media_type=media_type,
            filename=path.split("/")[-1],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Report generation failed: {exc}"
        )
