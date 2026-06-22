# 🏢 JLL 2026 Hackathon — ClimateNexus

**Problem Statements: #12 Climate-Risk Scoring & #13 Client Sustainability Strategy**
**Author: Anjali Gupta (Data Engineer)**

---

## One-Liner

> **"Score the risk. Prescribe the cure."**
> An end-to-end AI platform that scores climate risk on any property — then auto-generates a tailored sustainability strategy for the client.

---

## The Problem

JLL brokers and asset managers face two disconnected pain points:

| Pain Point | Current State | Impact |
|------------|---------------|--------|
| **Climate-risk assessment** | Fragmented across 8–12 data sources (FEMA, NOAA, local regs). Manual research takes **3–5 days per property**. | Deals delayed, risk mispriced, clients underserved |
| **Sustainability strategy** | Built manually by consultants using siloed playbooks. Takes **weeks per client**. | Can't scale advisory, brokers go to meetings without data |
| **The gap between them** | Risk scores sit in spreadsheets. Strategies don't reference actual risk data. | No connected value chain — risk insight never reaches the client action plan |

> Most teams will tackle scoring **or** strategy in isolation. ClimateNexus **connects both** — mirroring how JLL's advisory actually works: the sustainability team *needs* risk data to advise clients.

---

## The Solution: ClimateNexus

ClimateNexus chains the climate-risk score directly into a sustainability strategy recommendation engine. The risk score isn't just a number — it becomes the **input signal** that drives a tailored action plan.

### Pipeline Overview

```
                        ┌─────────────────────────┐
                        │     PROPERTY INPUT       │
                        │  (address or portfolio)  │
                        └────────────┬────────────┘
                                     ▼
                    ┌────────────────────────────────┐
                    │     STAGE 1: CLIMATE SCORING    │
                    │                                 │
                    │  • Multi-hazard data ingestion  │
                    │  • ML risk scoring engine        │
                    │  • Per-hazard sub-scores         │
                    │  • SHAP explainability           │
                    └────────────┬────────────────────┘
                                 ▼
                    ┌────────────────────────────────┐
                    │   BRIDGE: RISK → STRATEGY       │
                    │                                 │
                    │  Risk signals become agent      │
                    │  context:                       │
                    │  • High flood → resilience recs │
                    │  • High heat → cooling retrofits│
                    │  • High transition → compliance │
                    │    pathway acceleration         │
                    └────────────┬────────────────────┘
                                 ▼
                    ┌────────────────────────────────┐
                    │  STAGE 2: STRATEGY GENERATION   │
                    │                                 │
                    │  • RAG over sustainability KB    │
                    │  • Risk-aware recommendations    │
                    │  • ROI-ranked action plan        │
                    │  • Client-ready strategy deck    │
                    └────────────┬────────────────────┘
                                 ▼
                    ┌────────────────────────────────┐
                    │         DELIVERABLES            │
                    │                                 │
                    │  🗺️ Risk Heatmap (interactive)  │
                    │  📊 Climate Score Card           │
                    │  📑 Strategy Deck (auto-gen)     │
                    │  💰 Financial Impact Summary     │
                    │  📋 Regulatory Compliance Check  │
                    └────────────────────────────────┘
```

---

## Stage 1: Multi-Hazard Climate Risk Scoring

An ML-powered engine that ingests open climate data and produces an explainable **composite risk score (0–100)** per property.

### Hazard Dimensions

| Hazard | Data Source | Key Features |
|--------|------------|--------------|
| 🌊 **Flood** | FEMA NFHL (REST API) | Flood zone classification, SFHA status, base flood elevation, distance to zone boundary |
| 🌡️ **Heat Stress** | NOAA NCEI (REST API) | Climate normals, projected heat-stress days (RCP 4.5 & 8.5), cooling degree days |
| 🔥 **Wildfire** | NIFC / GeoMAC (GeoJSON) | Historical perimeters, burn probability, proximity to wildland-urban interface |
| ⚖️ **Transition Risk** | Local gov portals (scraped) | LL97 (NYC), BERDO (Boston), building performance standards, regulatory compliance gap |

### ML Architecture

| Component | Approach |
|-----------|----------|
| **Feature Engineering** | Geospatial features (PostGIS) + temporal features from public APIs |
| **Model** | XGBoost ensemble — per-hazard sub-models combined into composite score |
| **Training Data** | FEMA loss claims + insurance premium history (publicly available aggregates) |
| **Explainability** | SHAP values → shows exactly which hazards drive the score |
| **Financial Calibration** | Score mapped to expected annual loss (EAL) in dollar terms |

### Data Sources (all free / open — zero licensing cost)

| Source | Data | Access Method |
|--------|------|---------------|
| FEMA NFHL | Flood zones, base flood elevation | REST API (`hazards.fema.gov`) |
| NOAA NCEI | Historical weather extremes, climate normals | REST API |
| NIFC / GeoMAC | Wildfire perimeters & burn probability | GeoJSON download |
| USGS Elevation | Terrain elevation for flood modeling | REST API |
| First Street Foundation | Flood/fire/heat factor (limited free tier) | API |
| EPA ENERGY STAR | Building energy benchmarks | Portfolio Manager API |
| Local gov portals | Building performance standards (LL97, BERDO) | Web scraping (BeautifulSoup) |
| OpenStreetMap | Building footprints, land use | Overpass API |

---

## Stage 2: RAG-Powered Sustainability Strategy Agent

An AI agent that takes the risk scores and — through RAG over a sustainability knowledge base — generates a customized, client-ready action plan.

### Agent Architecture

**LLM Backbone:** Gemini 2.5 Pro / GPT-4o (via API)
**Orchestration:** LangGraph (state-machine agent framework for multi-step reasoning with tool use)

### Agent Tools

| Tool | Function |
|------|----------|
| 🔍 **RAG Retriever** | Queries sustainability knowledge base (LEED, LL97, IRA credits, technology specs) |
| 📊 **Portfolio Analyzer** | Parses client energy data, certifications, building profiles |
| 💲 **ROI Calculator** | Estimates retrofit costs, energy savings, payback period |
| 🌐 **Incentive Finder** | Matches property location to available rebates & tax credits (DSIRE database) |
| 📈 **Benchmark Tool** | Compares client buildings against ENERGY STAR peers |
| 📑 **Report Generator** | Creates client-ready strategy deck with visualizations |

### Knowledge Base (RAG)

| Category | Source | Ingestion Method |
|----------|--------|------------------|
| Certification standards | LEED v4.1, WELL v2, ENERGY STAR guides | Web scrape + PDF chunking → embedded |
| Regulations | LL97 (NYC), BERDO (Boston), EU Taxonomy, CSRD | Scraped from gov sites, structured in DB |
| Financial incentives | IRA tax credits, state/utility rebates | Scraped from DSIRE database |
| Technology catalog | Heat pumps, LED, solar, BMS upgrades | Curated CSV/JSON with specs, costs & ROI |
| Benchmark data | ENERGY STAR Portfolio Manager, GRESB | API + scraped |

**Vector Store:** ChromaDB (lightweight for hackathon) or pgvector
**Embeddings:** OpenAI `text-embedding-3-small` or Gemini embeddings

### Agent Workflow

```
Broker uploads portfolio
    ↓
Agent parses: building types, locations, energy use, certifications
    ↓
Agent queries RAG for relevant regulations per location
    ↓
Agent identifies compliance gaps & risks
    ↓
Agent queries RAG for applicable incentives & rebates
    ↓
Agent runs ROI calculator for retrofit options
    ↓
Agent ranks actions: quick wins → capex-heavy investments
    ↓
Agent generates sustainability strategy deck
    ↓
Broker reviews & refines via chat
    ↓
Final strategy delivered to client
```

---

## The Bridge: Risk → Strategy

This is the differentiator. The risk score doesn't just sit in a dashboard — it flows into the agent as context that shapes recommendations:

| Risk Signal | Strategy Response |
|-------------|-------------------|
| High flood score → | Flood barriers, elevated mechanicals, insurance renegotiation, FEMA mitigation grants |
| High heat score → | Cool-roof retrofits, HVAC upgrades, IRA tax credit paths, shade/greenery interventions |
| High wildfire score → | Ember-resistant materials, defensible space planning, wildfire insurance optimization |
| High transition risk → | Compliance pathway acceleration, certification roadmap (LEED/WELL), retrofit prioritization |

---

## Demo Scenario

> **"Imagine a JLL broker is pitching to a real estate fund with 50 properties across the US Southeast."**
>
> 1. **Upload:** Broker uploads a CSV of 50 property addresses
> 2. **Score:** In 30 seconds, ClimateNexus scores every property — **12 flagged high-risk for hurricane flooding**, **8 flagged for extreme heat**
> 3. **Strategize:** The AI agent automatically generates a tailored strategy:
>    - For the 12 flood-risk properties → flood barriers, elevated mechanicals, FEMA mitigation grants
>    - For the 8 heat-risk properties → cool-roof retrofits, HVAC upgrades, IRA tax credits
>    - For the full portfolio → net-zero roadmap with **$2.3M in incentives** and **34% energy cost reduction**
> 4. **Deliver:** A branded, client-ready strategy deck in PDF — ready for the Monday meeting

---

## Full Tech Stack

| Layer | Technology |
|-------|------------|
| **Data Ingestion** | Python + httpx/aiohttp for API calls, BeautifulSoup for scraping, PostGIS for geospatial storage |
| **ML Scoring** | XGBoost/LightGBM ensemble, SHAP for explainability, scikit-learn for preprocessing |
| **Vector Store** | ChromaDB (lightweight for hackathon) or pgvector |
| **Embeddings** | OpenAI `text-embedding-3-small` or Gemini embeddings |
| **LLM** | Gemini 2.5 Pro / GPT-4o (via API) |
| **Agent Framework** | LangGraph (preferred — state machine for multi-step reasoning) |
| **Frontend** | Streamlit (fast for hackathon) with Plotly/Folium for maps |
| **Report Gen** | Jinja2 templates → HTML → PDF (via WeasyPrint) |
| **Database** | PostgreSQL + PostGIS (or SQLite + SpatiaLite for hackathon) |

---

## Hackathon MVP Scope (48 Hours)

| Day | Task | Output |
|-----|------|--------|
| **Day 1 AM** | Set up data pipeline: FEMA flood + NOAA heat APIs. Geocoding service. PostGIS schema. | Working data ingestion for 2 hazards |
| **Day 1 PM** | Train XGBoost model on Miami/NYC data, build scoring API. Add SHAP explainability. | `/score?address=...` endpoint returning risk JSON |
| **Day 1 EVE** | Build RAG pipeline: ingest 15–20 sustainability docs into ChromaDB. Test retrieval. | ChromaDB populated, retrieval working |
| **Day 2 AM** | Build LangGraph agent: chain score → strategy generation. Wire up all tools. | Agent takes risk output, produces recommendations |
| **Day 2 PM** | Streamlit UI: map view + score cards + chat interface + PDF report download. | Full demo-ready frontend |
| **Day 2 EVE** | Polish demo scenario, generate sample reports, rehearse pitch. | Presentation-ready |

---

## Business Impact

| Metric | Before ClimateNexus | After ClimateNexus |
|--------|--------------------|--------------------|
| Risk assessment time | 3–5 days per property | **Seconds** |
| Strategy creation | Weeks per client | **Minutes** |
| Data licensing cost | Expensive vendor contracts | **$0** (100% open data) |
| Consultant throughput | ~5 clients/quarter | **10× more** |
| Scalability | Limited by headcount | **Any market, globally** |

### Who Benefits

- **Brokers** → Walk into client meetings with instant, data-backed climate intelligence
- **Asset Managers** → Portfolio-level risk heatmap with prioritized resilience investments
- **Clients** → Personalized sustainability roadmaps with real ROI — not generic advice
- **JLL** → Differentiate advisory services; win more mandates in sustainability consulting

---

## JLL Ecosystem Integration

ClimateNexus is designed to plug into JLL's existing technology platforms:

| Platform | Integration |
|----------|-------------|
| **JLL Falcon** | Risk scores feed into Falcon's market intelligence layer as a new signal |
| **JLL Azara** | Portfolio analytics enriched with climate risk as a first-class dimension |
| **Carbon Pathfinder** | Extend decarbonization roadmaps with risk-aware prioritization |
| **Sustainability Risk Advisory** | Auto-generate the first draft of advisory reports |

---

## Key Talking Points for the Pitch

### Why AI/ML is Essential
- **Climate data is massive and fragmented** — no human can synthesize FEMA, NOAA, satellite imagery, and local regulations for 50 properties manually
- **Pattern recognition** — ML models identify non-obvious correlations between climate features and property value impact
- **Personalization at scale** — RAG + Agents generate *bespoke* strategies per client without hiring more consultants

### JLL-Specific Hooks 🎯
- Integrates with **JLL Falcon** (market intelligence) and **JLL Azara** (analytics)
- Extends **Carbon Pathfinder** with climate-risk awareness
- Aligns with JLL's **Sustainability Risk Advisory** practice
- Addresses the **green premium / brown discount** that JLL's research team has documented

### Buzzwords That Land Well
`Geospatial ML` · `RAG-powered agents` · `Explainable AI (SHAP)` · `Multi-hazard scoring` · `Agentic workflows` · `LangGraph orchestration` · `Real-time climate intelligence` · `TCFD-aligned` · `Net-zero pathways`

---

*ClimateNexus — From fragmented climate data to client-ready sustainability strategies, in seconds, not weeks.* 🚀
