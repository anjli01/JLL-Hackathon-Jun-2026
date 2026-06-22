"""
Node implementations for the LangGraph sustainability strategy agent.

Each node takes AgentState, does its work, and returns a partial state update.
"""

import json
import logging
import os
from typing import Any

from src.agent.state import AgentState
from src.agent.tools.roi_calculator import ROICalculator
from src.agent.tools.incentive_finder import IncentiveFinder
from src.agent.tools.benchmark_tool import BenchmarkTool
from src.agent.tools.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

# Shared tool instances
_roi_calc = ROICalculator()
_incentive_finder = IncentiveFinder()
_benchmark = BenchmarkTool()
_report_gen = ReportGenerator()


# ---------------------------------------------------------------------------
# Risk → Strategy mapping (from Hackathon Ideas.md)
# ---------------------------------------------------------------------------

RISK_STRATEGY_MAP = {
    "flood": {
        "measures": ["flood_barriers", "elevated_mechanicals"],
        "description": "Flood barriers, elevated mechanicals, insurance renegotiation, FEMA mitigation grants",
    },
    "heat": {
        "measures": ["cool_roof", "heat_pump_ashp", "building_envelope"],
        "description": "Cool-roof retrofits, HVAC upgrades, IRA tax credit paths, shade/greenery",
    },
    "wildfire": {
        "measures": ["ember_resistant_roof"],
        "description": "Ember-resistant materials, defensible space planning, wildfire insurance optimization",
    },
    "transition": {
        "measures": ["led_lighting", "bms_upgrade", "heat_pump_ashp", "solar_pv"],
        "description": "Compliance pathway acceleration, certification roadmap, retrofit prioritization",
    },
    "seismic": {
        "measures": [],
        "description": "Structural assessment, seismic retrofit evaluation, insurance review",
    },
}


# =====================================================================
# Node 1: Analyze Risks
# =====================================================================


def analyze_risks(state: AgentState) -> dict:
    """
    Parse Stage 1 risk scores and identify top hazards per property.

    Pure Python — no LLM call. Groups properties by dominant hazard.
    """
    risk_scores = state.get("risk_scores", [])
    identified_risks: list[dict] = []

    for prop in risk_scores:
        address = prop.get("address", "Unknown")
        sub_scores = prop.get("sub_scores", {})
        raw = prop.get("raw_features", {})

        # Identify hazards above threshold
        hazards = []
        for hazard_name, score in sub_scores.items():
            if hazard_name == "elevation":
                continue  # Elevation is a flood amplifier, not standalone
            severity = "low"
            if score >= 70:
                severity = "high"
            elif score >= 40:
                severity = "medium"

            if score > 0:
                hazards.append({
                    "hazard": hazard_name,
                    "score": score,
                    "severity": severity,
                })

        # Sort by score descending
        hazards.sort(key=lambda h: h["score"], reverse=True)

        # Extract location info
        city = _extract_city(address)
        state_name = _extract_state(address)

        # Estimate building sqft from OSM data when available
        building_sqft = _estimate_building_sqft(
            building_levels=raw.get("building_levels"),
            building_type=raw.get("building_type_used", "office"),
            nearby_buildings=raw.get("nearby_buildings", 0),
        )

        identified_risks.append({
            "address": address,
            "composite_score": prop.get("composite_score", 0),
            "hazards": hazards,
            "top_hazard": hazards[0]["hazard"] if hazards else "none",
            "city": city,
            "state": state_name,
            "climate_zone": raw.get("climate_zone", 4),
            "building_type": raw.get("building_type_used", "office"),
            "building_sqft": building_sqft,
            "building_levels": raw.get("building_levels"),
            "eui": raw.get("climate_adjusted_eui"),
            "energy_star_score": raw.get("energy_star_score"),
            "flood_zone": raw.get("flood_zone", "Unknown"),
            "regulations": raw.get("applicable_regulations", []),
        })

    logger.info("Analyzed risks for %d properties", len(identified_risks))
    return {"identified_risks": identified_risks}


# =====================================================================
# Node 2: Retrieve Knowledge
# =====================================================================


def retrieve_knowledge(state: AgentState) -> dict:
    """
    Query the RAG knowledge base for each identified risk.

    Uses the RAG retriever tool injected via state or global reference.
    """
    from src.rag.vector_store import VectorStore

    identified_risks = state.get("identified_risks", [])

    # Build risk signals for the retriever
    risk_signals = []
    for prop in identified_risks:
        for hazard in prop.get("hazards", []):
            if hazard["severity"] in ("high", "medium"):
                risk_signals.append({
                    "hazard": hazard["hazard"],
                    "severity": hazard["severity"],
                    "location": f"{prop.get('city', '')} {prop.get('state', '')}",
                })

    # Deduplicate risk signals
    seen = set()
    unique_signals = []
    for sig in risk_signals:
        key = f"{sig['hazard']}_{sig['location']}"
        if key not in seen:
            seen.add(key)
            unique_signals.append(sig)

    # Query vector store
    try:
        vs = VectorStore()  # Uses existing persistent store
        from src.agent.tools.rag_retriever import RAGRetriever
        retriever = RAGRetriever(vs)
        chunks = retriever.retrieve_for_risks(unique_signals)
        logger.info("Retrieved %d knowledge chunks for %d risk signals", len(chunks), len(unique_signals))
    except Exception as exc:
        logger.warning("RAG retrieval failed: %s", exc)
        chunks = []

    return {"retrieved_context": chunks}


# =====================================================================
# Node 3: Find Incentives
# =====================================================================


def find_incentives(state: AgentState) -> dict:
    """Match property locations to available incentives and tax credits."""
    identified_risks = state.get("identified_risks", [])

    all_incentives: list[dict] = []
    seen_ids: set[str] = set()

    for prop in identified_risks:
        # Determine which measures would be recommended
        measures_for_prop = []
        for hazard in prop.get("hazards", []):
            strategy = RISK_STRATEGY_MAP.get(hazard["hazard"], {})
            measures_for_prop.extend(strategy.get("measures", []))

        # Find matching incentives
        matching = _incentive_finder.find_incentives(
            state=prop.get("state", ""),
            city=prop.get("city", ""),
            measures=measures_for_prop,
        )

        for inc in matching:
            if inc["id"] not in seen_ids:
                seen_ids.add(inc["id"])
                all_incentives.append(inc)

    logger.info("Found %d unique incentives", len(all_incentives))
    return {"incentives": all_incentives}


# =====================================================================
# Node 4: Calculate ROI
# =====================================================================


def calculate_roi(state: AgentState) -> dict:
    """Run ROI calculations for each recommended retrofit measure."""
    identified_risks = state.get("identified_risks", [])

    all_options: list[dict] = []
    seen_measures: set[str] = set()

    for prop in identified_risks:
        for hazard in prop.get("hazards", []):
            if hazard["severity"] not in ("high", "medium"):
                continue

            strategy = RISK_STRATEGY_MAP.get(hazard["hazard"], {})
            for measure_id in strategy.get("measures", []):
                if measure_id in seen_measures:
                    continue
                seen_measures.add(measure_id)

                roi = _roi_calc.calculate_roi(
                    measure_id=measure_id,
                    building_sqft=prop.get("building_sqft", 50000),
                    climate_zone=prop.get("climate_zone", 4),
                )
                if "error" not in roi:
                    roi["affected_addresses"] = [
                        p["address"]
                        for p in identified_risks
                        if any(h["hazard"] in RISK_STRATEGY_MAP.get(hazard["hazard"], {}).get("measures", [])
                               for h in p.get("hazards", []) if h["severity"] in ("high", "medium"))
                    ]
                    # Simplify: just add addresses where this hazard is relevant
                    roi["affected_addresses"] = [
                        p["address"]
                        for p in identified_risks
                        if any(h["hazard"] == hazard["hazard"] and h["severity"] in ("high", "medium")
                               for h in p.get("hazards", []))
                    ]
                    all_options.append(roi)

    # Run benchmark for each property
    benchmarks = []
    for prop in identified_risks:
        bm = _benchmark.benchmark(
            building_type=prop.get("building_type", "office"),
            current_eui=92.9,  # default if unknown
            climate_zone=prop.get("climate_zone", 4),
        )
        bm["address"] = prop["address"]
        benchmarks.append(bm)

    logger.info("Calculated ROI for %d measures", len(all_options))
    return {
        "retrofit_options": all_options,
        "benchmark_results": benchmarks,
    }


# =====================================================================
# Node 5: Generate Strategy (LLM)
# =====================================================================


def generate_strategy(state: AgentState) -> dict:
    """
    Use LLM to synthesize all context into a ranked strategy narrative.

    Falls back to a template-based strategy if no LLM API key is available.
    """
    identified_risks = state.get("identified_risks", [])
    retrieved_context = state.get("retrieved_context", [])
    retrofit_options = state.get("retrofit_options", [])
    incentives = state.get("incentives", [])
    benchmark_results = state.get("benchmark_results", [])
    user_query = state.get("user_query", "")

    # Build recommendations from ROI data
    recommendations = _build_recommendations(
        retrofit_options, incentives, identified_risks
    )

    # Calculate totals
    total_savings = sum(r.get("estimated_annual_savings_usd", 0) for r in recommendations)
    total_cost = sum(r.get("estimated_cost_usd", 0) for r in recommendations)

    # Estimate incentive value
    total_incentives = _incentive_finder.estimate_total_incentive_value(
        incentives, total_cost
    )

    # Try LLM-generated narrative, fall back to template
    narrative = _generate_narrative_llm(
        identified_risks, retrieved_context, recommendations,
        incentives, total_savings, total_incentives, user_query
    )

    return {
        "recommendations": recommendations,
        "strategy_narrative": narrative,
        "total_incentives_usd": total_incentives,
        "total_savings_usd": total_savings,
        "messages": state.get("messages", []) + [
            {"role": "assistant", "content": narrative}
        ],
    }


# =====================================================================
# Node 6: Refine Strategy (Chat)
# =====================================================================


def refine_strategy(state: AgentState) -> dict:
    """Handle follow-up chat — queries RAG and refines strategy."""
    user_query = state.get("user_query", "")
    current_narrative = state.get("strategy_narrative", "")
    recommendations = state.get("recommendations", [])
    messages = state.get("messages", [])

    # Add user message
    messages = messages + [{"role": "user", "content": user_query}]

    # ------------------------------------------------------------------
    # Step 1: Query RAG for relevant context based on the user's question
    # ------------------------------------------------------------------
    rag_context = ""
    try:
        from src.rag.vector_store import VectorStore
        vs = VectorStore()
        rag_chunks = vs.query(user_query, n_results=5)
        if rag_chunks:
            rag_context = "\n\n".join([
                f"[{c['source']}]: {c['text'][:400]}"
                for c in rag_chunks
            ])
            logger.info("RAG retrieval for chat: %d chunks", len(rag_chunks))
    except Exception as exc:
        logger.warning("RAG retrieval in chat failed: %s", exc)

    # ------------------------------------------------------------------
    # Step 2: Build strategy context summary for the LLM
    # ------------------------------------------------------------------
    strategy_context = ""
    if recommendations:
        rec_lines = []
        for i, rec in enumerate(recommendations, 1):
            props = ", ".join(rec.get("affected_properties", [])[:3])
            rec_lines.append(
                f"{i}. [{rec.get('priority', 'N/A').upper()}] {rec.get('action', 'N/A')} — "
                f"Cost: ${rec.get('estimated_cost_usd', 0):,.0f}, "
                f"Savings: ${rec.get('estimated_annual_savings_usd', 0):,.0f}/yr"
                f"{f' — Properties: {props}' if props else ''}"
            )
        strategy_context = "Current Recommendations:\n" + "\n".join(rec_lines)

    if current_narrative:
        # Include first 500 chars of the narrative for context
        strategy_context += f"\n\nStrategy Summary:\n{current_narrative[:500]}"

    # ------------------------------------------------------------------
    # Step 3: Generate response via LLM (or template fallback)
    # ------------------------------------------------------------------
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        try:
            from google import genai

            client = genai.Client(api_key=api_key)

            system_prompt = (
                "You are ClimateNexus, a sustainability strategy AI agent for commercial real estate. "
                "You have already generated a strategy for the broker's portfolio. "
                "The broker is now asking follow-up questions. "
                "Use the Knowledge Base Context and Current Strategy to give specific, actionable answers. "
                "Reference specific recommendations, incentive amounts, and property addresses when relevant."
            )

            context_block = ""
            if strategy_context:
                context_block += f"\n\n## Current Strategy\n{strategy_context}"
            if rag_context:
                context_block += f"\n\n## Knowledge Base Context\n{rag_context}"

            full_system = system_prompt + context_block

            chat_messages = [{"role": "user", "parts": [{"text": full_system}]}]
            chat_messages.append({"role": "model", "parts": [{"text": "I understand. I'm ready to help refine the strategy."}]})

            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                chat_messages.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}],
                })

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=chat_messages,
            )
            reply = response.text
        except Exception as exc:
            logger.warning("LLM chat failed: %s", exc)
            reply = (
                f"I'd be happy to discuss that further. Regarding '{user_query}' — "
                f"the current strategy includes {len(recommendations)} recommendations. "
                f"Could you specify which aspect you'd like me to elaborate on?"
            )
    else:
        reply = (
            f"Regarding '{user_query}': The current strategy includes "
            f"{len(recommendations)} recommendations. "
            f"Please set GOOGLE_API_KEY to enable AI-powered refinement."
        )

    messages = messages + [{"role": "assistant", "content": reply}]

    return {
        "strategy_narrative": reply,
        "messages": messages,
    }


# =====================================================================
# Node 7: Generate Report
# =====================================================================


def generate_report(state: AgentState) -> dict:
    """Render the finalized strategy into an HTML/PDF report."""
    portfolio_summary = state.get("portfolio_summary", {})
    recommendations = state.get("recommendations", [])
    narrative = state.get("strategy_narrative", "")
    identified_risks = state.get("identified_risks", [])
    risk_scores = state.get("risk_scores", [])

    # Build risk_details for the heatmap section (per-property sub-scores)
    risk_details = []
    for prop in risk_scores:
        risk_details.append({
            "address": prop.get("address", "Unknown"),
            "composite_score": prop.get("composite_score", 0),
            "sub_scores": prop.get("sub_scores", {}),
        })

    # Build regulation data for the compliance roadmap
    regulations = _build_regulation_data(identified_risks)

    strategy_data = {
        "property_count": portfolio_summary.get("total_properties", 0),
        "portfolio_summary": portfolio_summary,
        "strategy_narrative": narrative,
        "recommendations": recommendations,
        "total_incentives_usd": state.get("total_incentives_usd", 0),
        "total_savings_usd": state.get("total_savings_usd", 0),
        "risk_details": risk_details,
        "regulations": regulations,
    }

    try:
        html_path = _report_gen.save_html(strategy_data)
        # Try PDF too
        try:
            pdf_path = _report_gen.save_pdf(strategy_data)
            report_path = pdf_path
        except Exception:
            report_path = html_path
    except Exception as exc:
        logger.error("Report generation failed: %s", exc)
        report_path = None

    return {"report_path": report_path}


# =====================================================================
# Internal helpers
# =====================================================================


def _extract_city(address: str) -> str:
    """Extract city name from address string."""
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 2:
        return parts[1].strip()
    return ""


def _extract_state(address: str) -> str:
    """Extract state from address string."""
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 3:
        # Handle "NY 10041" or "Florida"
        state_part = parts[2].strip()
        return state_part.split()[0] if state_part else ""
    return ""


# ---- Building size estimation from OSM data ----

# Typical commercial floor plate sizes (sqft per floor)
_FLOOR_PLATE_DEFAULTS = {
    "office": 20000,
    "commercial": 15000,
    "retail": 12000,
    "industrial": 30000,
    "warehouse": 40000,
    "hotel": 10000,
    "apartments": 8000,
    "residential": 8000,
    "hospital": 25000,
    "school": 18000,
    "university": 20000,
    "yes": 15000,  # OSM default when type is unspecified
}

# Default total sqft when no OSM data is available
_DEFAULT_SQFT_BY_TYPE = {
    "office": 50000,
    "commercial": 40000,
    "retail": 25000,
    "industrial": 60000,
    "warehouse": 80000,
    "hotel": 80000,
    "apartments": 30000,
    "residential": 2500,
    "hospital": 150000,
    "school": 60000,
    "university": 100000,
}


def _estimate_building_sqft(
    building_levels: int | None,
    building_type: str = "office",
    nearby_buildings: int = 0,
) -> int:
    """
    Estimate building sqft from OSM data.

    Strategy:
    - If building_levels is known → floor_plate × levels
    - Otherwise → use default by building type
    - Adjust upward for dense urban areas (many nearby buildings)
    """
    btype = (building_type or "office").lower()
    floor_plate = _FLOOR_PLATE_DEFAULTS.get(btype, 15000)

    if building_levels and building_levels > 0:
        base_sqft = floor_plate * building_levels
    else:
        base_sqft = _DEFAULT_SQFT_BY_TYPE.get(btype, 50000)

    # Urban density adjustment: more nearby buildings → likely larger
    if nearby_buildings and nearby_buildings > 10:
        base_sqft = int(base_sqft * 1.2)

    return base_sqft


# ---- Regulation data for compliance roadmap ----

# Known building performance regulations with details
_REGULATION_DATABASE = {
    "Local Law 97 (LL97)": {
        "jurisdiction": "New York City",
        "requirement": "Carbon emissions caps for buildings >25,000 sq ft. Buildings must reduce emissions 40% by 2030 and 80% by 2050 vs 2005 baseline.",
        "deadline": "2024 (first compliance period), 2030 (stricter caps)",
        "penalty": "$268 per metric ton of CO2 over the limit, annually",
        "pathway": "Electrify heating (heat pumps), upgrade building envelope, install BMS, pursue ENERGY STAR certification",
        "location_match": ["ny", "new york", "nyc", "manhattan", "brooklyn", "queens", "bronx"],
    },
    "BERDO 2.0": {
        "jurisdiction": "Boston, MA",
        "requirement": "Building Emissions Reduction and Disclosure Ordinance — net-zero emissions by 2050 for buildings >20,000 sq ft.",
        "deadline": "2025 (reporting begins), 2030 (first compliance period)",
        "penalty": "$150–$300 per day of non-compliance",
        "pathway": "Electrification roadmap, on-site renewables, green energy procurement, MassSave rebate programs",
        "location_match": ["boston", "ma", "massachusetts"],
    },
    "Title 24 (California Building Code)": {
        "jurisdiction": "California",
        "requirement": "All-electric new construction mandate. Existing buildings must meet energy efficiency standards during major renovations.",
        "deadline": "2023 (new construction), 2026 (major renovations)",
        "penalty": "Permit denial, stop-work orders",
        "pathway": "Heat pump HVAC, induction cooking, solar PV + battery storage",
        "location_match": ["ca", "california", "los angeles", "san francisco", "san diego"],
    },
    "Chicago Energy Benchmarking": {
        "jurisdiction": "Chicago, IL",
        "requirement": "Annual energy use reporting for buildings >50,000 sq ft via ENERGY STAR Portfolio Manager.",
        "deadline": "Annual reporting by June 1",
        "penalty": "Fines up to $100/day for non-compliance",
        "pathway": "ENERGY STAR certification, LED lighting, BMS upgrades",
        "location_match": ["chicago", "il", "illinois"],
    },
}


def _build_regulation_data(identified_risks: list[dict]) -> list[dict]:
    """Build regulation entries for the compliance roadmap section."""
    regulations: list[dict] = []
    matched_regs: dict[str, list[str]] = {}  # reg_name -> [addresses]

    for prop in identified_risks:
        location = f"{prop.get('city', '')} {prop.get('state', '')}".lower()
        address = prop.get("address", "Unknown")

        # Check explicit regulations from Stage 1
        for reg_name in prop.get("regulations", []):
            if reg_name not in matched_regs:
                matched_regs[reg_name] = []
            matched_regs[reg_name].append(address)

        # Also check by location against our regulation database
        for reg_name, reg_info in _REGULATION_DATABASE.items():
            if any(loc in location for loc in reg_info["location_match"]):
                if reg_name not in matched_regs:
                    matched_regs[reg_name] = []
                if address not in matched_regs[reg_name]:
                    matched_regs[reg_name].append(address)

    for reg_name, addresses in matched_regs.items():
        reg_info = _REGULATION_DATABASE.get(reg_name, {})
        regulations.append({
            "name": reg_name,
            "jurisdiction": reg_info.get("jurisdiction", "Unknown"),
            "affected_properties": addresses,
            "requirement": reg_info.get("requirement", "Building performance standard"),
            "deadline": reg_info.get("deadline", "Check local requirements"),
            "penalty": reg_info.get("penalty", "Varies"),
            "pathway": reg_info.get("pathway", "Energy efficiency improvements"),
        })

    return regulations

def _build_recommendations(
    retrofit_options: list[dict],
    incentives: list[dict],
    identified_risks: list[dict],
) -> list[dict]:
    """Build ranked recommendation items from ROI data."""
    recommendations = []

    # Sort by payback (quick wins first, then risk avoidance)
    sorted_options = sorted(
        retrofit_options,
        key=lambda x: (x.get("payback_years") or 999, -x.get("annual_savings_mid", 0)),
    )

    for opt in sorted_options:
        payback = opt.get("payback_years")
        if payback and payback <= 4:
            priority = "quick_win"
        elif payback and payback <= 8:
            priority = "medium_term"
        else:
            priority = "capex_heavy"

        # Find applicable incentives
        applicable = [
            inc["name"]
            for inc in incentives
            if opt["measure_id"] in [
                m for i in [
                    i2 for i2 in _incentive_finder.incentives
                    if i2["id"] == inc["id"]
                ] for m in i.get("eligible_measures", [])
            ]
        ]

        recommendations.append({
            "category": opt.get("category", "general"),
            "action": opt.get("name", "Unknown"),
            "priority": priority,
            "affected_properties": opt.get("affected_addresses", []),
            "estimated_cost_usd": opt.get("cost_estimate_mid", 0),
            "estimated_annual_savings_usd": opt.get("annual_savings_mid", 0),
            "payback_years": payback,
            "applicable_incentives": applicable,
            "rationale": opt.get("description", ""),
        })

    return recommendations


def _generate_narrative_llm(
    identified_risks: list[dict],
    retrieved_context: list[dict],
    recommendations: list[dict],
    incentives: list[dict],
    total_savings: float,
    total_incentives: float,
    user_query: str,
) -> str:
    """Generate strategy narrative using Gemini LLM (or fallback to template)."""
    api_key = os.environ.get("GOOGLE_API_KEY")

    if not api_key:
        return _generate_narrative_template(
            identified_risks, recommendations, total_savings, total_incentives
        )

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        # Build context
        risk_summary = json.dumps(
            [{
                "address": r["address"],
                "score": r["composite_score"],
                "top_hazard": r["top_hazard"],
                "hazards": [{"name": h["hazard"], "score": h["score"], "severity": h["severity"]}
                           for h in r["hazards"]],
                "regulations": r.get("regulations", []),
            } for r in identified_risks],
            indent=2,
        )

        rag_context = "\n\n".join([
            f"[{c['source']}]: {c['text'][:300]}"
            for c in retrieved_context[:10]
        ])

        rec_summary = json.dumps(
            [{
                "action": r["action"],
                "priority": r["priority"],
                "cost": r["estimated_cost_usd"],
                "savings": r["estimated_annual_savings_usd"],
                "payback": r["payback_years"],
            } for r in recommendations],
            indent=2,
        )

        prompt = f"""You are ClimateNexus, an AI sustainability strategy agent for commercial real estate.

Generate a concise, professional executive summary for a portfolio sustainability strategy report.

## Portfolio Risk Analysis
{risk_summary}

## Relevant Knowledge Base Context
{rag_context}

## Recommended Actions
{rec_summary}

## Financial Summary
- Total estimated annual savings: ${total_savings:,.0f}
- Total available incentives: ${total_incentives:,.0f}
- Number of incentive programs matched: {len(incentives)}

{f"Broker's specific request: {user_query}" if user_query else ""}

Write 3-4 paragraphs covering:
1. Portfolio risk overview (which hazards dominate, which properties are highest risk)
2. Key recommended actions (prioritized: quick wins → capital investments)
3. Financial opportunity (savings, incentives, ROI)
4. Regulatory compliance pathway (if applicable regulations were identified)

Be specific with numbers and property addresses. Use professional advisory tone suitable for a JLL broker presentation."""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text

    except Exception as exc:
        logger.warning("LLM narrative generation failed: %s — using template", exc)
        return _generate_narrative_template(
            identified_risks, recommendations, total_savings, total_incentives
        )


def _generate_narrative_template(
    identified_risks: list[dict],
    recommendations: list[dict],
    total_savings: float,
    total_incentives: float,
) -> str:
    """Template-based fallback narrative when LLM is unavailable."""
    n_props = len(identified_risks)
    high_risk = [r for r in identified_risks if r["composite_score"] >= 70]
    med_risk = [r for r in identified_risks if 40 <= r["composite_score"] < 70]

    # Top hazards
    hazard_counts: dict[str, int] = {}
    for r in identified_risks:
        h = r.get("top_hazard", "unknown")
        hazard_counts[h] = hazard_counts.get(h, 0) + 1
    top_hazard = max(hazard_counts, key=hazard_counts.get) if hazard_counts else "none"

    quick_wins = [r for r in recommendations if r["priority"] == "quick_win"]
    capex = [r for r in recommendations if r["priority"] == "capex_heavy"]

    lines = [
        f"<p><strong>Portfolio Overview:</strong> Analysis of {n_props} properties identified "
        f"{len(high_risk)} high-risk and {len(med_risk)} medium-risk assets. "
        f"The dominant hazard across the portfolio is <strong>{top_hazard}</strong>, "
        f"affecting {hazard_counts.get(top_hazard, 0)} properties.</p>",

        f"<p><strong>Recommended Actions:</strong> {len(recommendations)} retrofit measures have been identified. "
        f"{len(quick_wins)} are quick wins with payback under 4 years, while "
        f"{len(capex)} require significant capital investment for long-term resilience.</p>",

        f"<p><strong>Financial Opportunity:</strong> Combined annual savings of "
        f"<strong>${total_savings:,.0f}</strong> are achievable, with "
        f"<strong>${total_incentives:,.0f}</strong> in available tax credits, rebates, "
        f"and grant funding to offset retrofit costs.</p>",
    ]

    # Add regulation note if applicable
    regs = set()
    for r in identified_risks:
        for reg in r.get("regulations", []):
            regs.add(reg)
    if regs:
        lines.append(
            f"<p><strong>Regulatory Compliance:</strong> {', '.join(regs)} "
            f"apply to properties in this portfolio. Proactive compliance through "
            f"the recommended measures will avoid penalties and position assets "
            f"for green premium valuation.</p>"
        )

    return "\n".join(lines)
