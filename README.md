<div align="center">

# 🏢 ClimateNexus

### Score the risk. Prescribe the cure.

An end-to-end AI platform that scores multi-hazard climate risk on any commercial property — then auto-generates a tailored sustainability strategy with ROI-ranked action plans.

**Built for the JLL 2026 Hackathon** · Problem Statements #12 & #13

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent-1C3C3C?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)

</div>

---

## 🔍 Overview

JLL brokers and asset managers face two disconnected pain points: **climate-risk assessment** (fragmented across 8–12 data sources, taking 3–5 days per property) and **sustainability strategy** (built manually by consultants over weeks). ClimateNexus **connects both** — mirroring how JLL's advisory actually works.

### What It Does

| Stage | Function | Time |
|-------|----------|------|
| **Stage 1 — Risk Scoring** | Ingests real-time data from 8 public APIs (FEMA, NOAA, USGS, USFS, OpenStreetMap, EPA), runs ML scoring across 6 hazard dimensions, and produces an explainable composite risk score (0–100) per property | **Seconds** |
| **Stage 2 — Strategy Agent** | RAG-powered LangGraph agent takes the risk scores, retrieves relevant regulations/incentives from a curated knowledge base (14 docs), calculates retrofit ROI, and auto-generates a ranked sustainability action plan | **Minutes** |
| **Frontend** | Streamlit multi-page app with interactive map, score cards, SHAP waterfall charts, chat-based strategy refinement, and downloadable HTML/PDF report | **Real-time** |

### Key Benefits

- **8 real-time data sources** — zero licensing cost, 100% open/public data
- **6 hazard dimensions** — flood, heat stress, wildfire, seismic, transition risk, elevation
- **Explainable AI** — SHAP-style decomposition shows exactly which hazards drive the score
- **Financial calibration** — scores mapped to Expected Annual Loss (EAL) in USD
- **Risk-aware strategy** — recommendations are driven by actual risk data, not generic templates
- **ROI-ranked actions** — each recommendation includes cost, annual savings, payback period, and applicable incentives (IRA tax credits, state rebates)
- **Batch scoring** — score entire portfolios (up to 200 properties) via JSON or CSV upload

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Google API Key** (for Gemini LLM in Stage 2) — set as `GOOGLE_API_KEY` in `.env`

> [!NOTE]
> Stage 1 (risk scoring) works entirely without an API key.  
> Stage 2 falls back to template-based responses if no `GOOGLE_API_KEY` is set.

### Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/ClimateNexus.git
cd ClimateNexus

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# (Optional) Set up environment variables
echo 'GOOGLE_API_KEY=your-key-here' > .env
```

### Run the API Server

```bash
uvicorn src.api.main:app --reload
```

The API will be available at:
- **Swagger UI** — [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc** — [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### Run the Frontend

```bash
streamlit run streamlit/app.py
```

Opens at [http://localhost:8501](http://localhost:8501).

### Run the Tests

```bash
pip install pytest-asyncio

# Unit tests (fast, offline — all HTTP calls mocked)
pytest tests/unit/ -v

# Integration tests (requires the API server to be running)
python tests/integration/test_full_flow.py
```

### Quick Test with cURL

```bash
curl -X POST http://127.0.0.1:8000/score \
  -H "Content-Type: application/json" \
  -d '{"address": "350 5th Ave, New York, NY 10118"}'
```

---

## 🏗️ Architecture

### System Data Flow

```
┌──────────────────────────────────┐
│        PROPERTY INPUT            │
│   (address or CSV portfolio)     │
└───────────────┬──────────────────┘
                ▼
┌──────────────────────────────────┐
│   STAGE 1: CLIMATE RISK SCORING  │
│                                  │
│  Nominatim Geocoder              │
│        │                         │
│        ▼                         │
│  ┌──────────────────────────┐    │
│  │   asyncio.gather (8 APIs)│    │
│  │  ┌─────┐ ┌─────┐ ┌────┐ │    │
│  │  │FEMA │ │NOAA │ │USFS│ │    │
│  │  └─────┘ └─────┘ └────┘ │    │
│  │  ┌─────┐ ┌─────┐ ┌────┐ │    │
│  │  │USGS │ │USGS │ │ OSM│ │    │
│  │  │Elev.│ │Seis.│ └────┘ │    │
│  │  └─────┘ └─────┘   │    │    │
│  │  ┌─────┐     ┌─────┘    │    │
│  │  │Tran.│     │EPA Energy│    │
│  │  └─────┘     └──────────┘    │
│  └──────────────────────────┘    │
│        │                         │
│        ▼                         │
│  XGBoost Ensemble → SHAP        │
│  (6-hazard weighted scoring)     │
│        │                         │
│        ▼                         │
│  SQLite Feature Cache            │
└───────────────┬──────────────────┘
                ▼
┌──────────────────────────────────┐
│  STAGE 2: STRATEGY GENERATION    │
│                                  │
│  LangGraph Agent Pipeline:       │
│  analyze → retrieve → incentives │
│  → ROI calc → generate strategy  │
│                                  │
│  ChromaDB ← 14 knowledge docs   │
│  Gemini 2.5 Flash (LLM)         │
└───────────────┬──────────────────┘
                ▼
┌──────────────────────────────────┐
│         DELIVERABLES             │
│                                  │
│  📊 Risk Score (0–100)           │
│  📈 SHAP Explainability          │
│  💰 ROI-Ranked Recommendations   │
│  📑 Strategy Report (HTML/PDF)   │
│  💬 Chat Refinement              │
└──────────────────────────────────┘
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/score` | Score a single property for multi-hazard climate risk |
| `POST` | `/score/batch` | Score multiple properties (JSON list, max 200) |
| `POST` | `/score/upload-csv` | Score a portfolio from CSV upload |
| `POST` | `/agent/strategize` | Generate sustainability strategy for scored properties |
| `POST` | `/agent/chat` | Chat-based strategy refinement with context |
| `POST` | `/agent/report` | Generate downloadable HTML/PDF strategy report |

### Data Sources

| Source | API | Hazard Data |
|--------|-----|-------------|
| **FEMA NFHL** | MapServer REST | Flood zone, SFHA status, base flood elevation |
| **NOAA RCC-ACIS** | GridData REST | 30-year climate normals, extreme heat days, CDD, RCP projections |
| **USFS Wildfire Risk** | ImageServer REST | Annual burn probability |
| **USGS Elevation** | EPQS REST | Terrain elevation, low-lying flag |
| **USGS Seismic** | Design Maps REST | SDS, SD1, PGA, seismic design category |
| **OpenStreetMap** | Overpass API | Building type, floors, land use, nearby buildings |
| **EPA ENERGY STAR** | SODA API + benchmarks | Median EUI by building type, climate-zone adjustment |
| **Transition Rules** | Rule-based engine | LL97 (NYC), BERDO (Boston), Title 24 (CA), and more |

---

## 📂 Codebase Walkthrough

```
├── src/                             ← Application source code
│   ├── api/                         ← FastAPI layer
│   │   ├── main.py                  ←   Endpoints, geocoder, orchestration
│   │   └── models.py               ←   Pydantic request/response schemas
│   │
│   ├── ingestion/                   ← Real-time data clients (all async)
│   │   ├── fema_client.py           ←   FEMA NFHL flood zone lookup
│   │   ├── noaa_client.py           ←   NOAA RCC-ACIS 30-year climate normals
│   │   ├── wildfire_client.py       ←   USFS burn probability
│   │   ├── usgs_elevation_client.py ←   USGS terrain elevation
│   │   ├── usgs_seismic_client.py   ←   USGS earthquake design parameters
│   │   ├── osm_client.py           ←   OpenStreetMap building metadata
│   │   ├── epa_energy_star_client.py←   EPA ENERGY STAR benchmarks
│   │   └── transition_client.py     ←   Local regulation matching engine
│   │
│   ├── db/                          ← Persistence layer
│   │   ├── schema.sql               ←   SQLite table definitions
│   │   └── feature_store.py         ←   Cache with TTL-based expiry
│   │
│   ├── ml/                          ← Scoring engine
│   │   ├── xgboost_ensemble.py      ←   6-hazard weighted composite scorer
│   │   └── explainer.py             ←   SHAP-style feature importance
│   │
│   ├── rag/                         ← RAG pipeline
│   │   ├── vector_store.py          ←   ChromaDB wrapper (Gemini embeddings)
│   │   ├── knowledge_loader.py      ←   Document chunker & loader
│   │   └── knowledge/               ←   14 curated sustainability docs
│   │
│   └── agent/                       ← LangGraph strategy agent
│       ├── state.py                 ←   TypedDict agent state schema
│       ├── graph.py                 ←   State machine (strategy/chat/report)
│       ├── nodes.py                 ←   Node implementations (analyze, retrieve, etc.)
│       └── tools/                   ←   Agent tools
│           ├── rag_retriever.py     ←     Semantic search over knowledge base
│           ├── roi_calculator.py    ←     Retrofit cost/savings/payback calculator
│           ├── incentive_finder.py  ←     IRA credits & state rebate matcher
│           ├── benchmark_tool.py    ←     ENERGY STAR peer comparison
│           └── report_generator.py  ←     Jinja2 → HTML/PDF report renderer
│
├── streamlit/                       ← Frontend
│   ├── app.py                       ←   Landing page & session state
│   └── pages/
│       ├── 1_🗺️_Portfolio_Scorer.py ←   CSV upload, map, score cards
│       ├── 2_📊_Strategy_Agent.py   ←   Strategy generation & recommendations
│       ├── 3_💬_Chat_Refinement.py  ←   Conversational strategy refinement
│       └── 4_📑_Report_Download.py  ←   PDF/HTML report generation
│
├── tests/
│   ├── unit/                        ←   25 offline tests (mocked HTTP)
│   └── integration/                 ←   End-to-end tests (live API)
│
└── docs/                            ← Documentation
    ├── ideation/                    ←   Hackathon ideas, pitch deck, photos
    ├── architecture/                ←   System & codebase diagrams (Mermaid)
    ├── plans/                       ←   Implementation plans (Stage 1, 2, UI)
    └── walkthroughs/                ←   Build logs & review transcripts
```

### How the Scoring Pipeline Works

1. **Geocode** — Address → lat/lon via Nominatim
2. **Parallel Fetch** — 8 API clients fire concurrently via `asyncio.gather`
3. **Merge** — All features merged into a single dict (35+ fields)
4. **Cache** — Features persisted to SQLite (24-hour TTL)
5. **Score** — XGBoost ensemble computes composite score (0–100) across 6 hazards
6. **Explain** — SHAP explainer decomposes the score into per-hazard impact values
7. **Return** — Structured JSON with score, sub-scores, SHAP values, and raw features

### How the Strategy Agent Works

1. **Analyze Risks** — Parses Stage 1 scores, identifies top hazards per property
2. **Retrieve Knowledge** — Queries ChromaDB for relevant regulations, tech specs, and best practices
3. **Find Incentives** — Matches property location to IRA credits, state rebates (10 programs)
4. **Calculate ROI** — Estimates cost, annual savings, payback for 9 retrofit measures
5. **Generate Strategy** — LLM synthesizes everything into a ranked action plan with narrative
6. **Refine (Chat)** — Broker asks follow-up questions; agent refines recommendations
7. **Report** — Jinja2 template renders a 6-section HTML/PDF strategy deck

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **API Framework** | FastAPI + Uvicorn |
| **Data Ingestion** | httpx (async HTTP), 8 public REST APIs |
| **ML Scoring** | XGBoost-style weighted ensemble, SHAP explainability |
| **Database** | SQLite (feature cache with TTL) |
| **Vector Store** | ChromaDB (persistent, Gemini embeddings) |
| **LLM** | Google Gemini 2.5 Flash (via LangChain) |
| **Agent Framework** | LangGraph (state-machine orchestration) |
| **RAG** | 14 curated markdown docs, 800-token chunks |
| **Report Generation** | Jinja2 → HTML → PDF (WeasyPrint) |
| **Frontend** | Streamlit (multi-page app), Folium maps, Plotly charts |
| **Testing** | pytest + pytest-asyncio (25 unit tests) |

---

## 📊 Demo Scenario

> *"Imagine a JLL broker pitching to a real estate fund with properties across the US."*

1. **Upload** — Broker uploads a CSV of property addresses
2. **Score** — In seconds, ClimateNexus scores every property — flagging high-risk for flooding, extreme heat, seismic
3. **Strategize** — AI agent auto-generates a tailored strategy: flood barriers for coastal properties, cool-roof retrofits for heat-stressed ones, LL97 compliance for NYC
4. **Refine** — Broker chats with the agent: *"What about solar?"* → agent adds solar PV with IRA 30% ITC
5. **Deliver** — A branded, client-ready strategy deck — ready for the Monday meeting

---

## 🧪 Sample Test Addresses

Use these prominent U.S. corporate office addresses to test the scoring engine across different risk profiles. You can paste them directly into the **Batch Addresses** tab of the Streamlit Portfolio Scorer, or use the `/score/batch` API endpoint.

### 🌊 High Flood & Hurricane Risk (Gulf / East Coast)

These addresses are prone to coastal flooding, storm surges, and hurricanes.

| Building | Address |
|----------|---------|
| Hancock Whitney Center | `701 Poydras St, New Orleans, LA 70139` |
| Enterprise Plaza | `1100 Louisiana Street, Houston, TX 77002` |
| Brickell World Plaza | `600 Brickell Ave, Miami, FL 33131` |
| 101 Seaport (PwC) | `101 Seaport Blvd, Boston, MA 02210` |

> **Expected:** High flood sub-scores (60–90), FEMA Zone AE/VE, SFHA = true, low elevation flags for coastal properties.

### 🌋 High Seismic & Transition Risk (West Coast)

These addresses face high earthquake probabilities. California buildings also flag high "Transition Risk" due to strict regulations like Title 24.

| Building | Address |
|----------|---------|
| Salesforce Tower | `415 Mission Street, San Francisco, CA 94105` |
| Bank of America Plaza | `333 S Hope St, Los Angeles, CA 90071` |
| Columbia Center | `701 5th Ave, Seattle, WA 98104` |

> **Expected:** Seismic Design Category D–E, high SDS values, `applicable_regulations` includes California Title 24.

### 🌡️ High Extreme Heat Risk (Southwest)

These locations face rapidly increasing extreme heat days and high cooling degree days (CDD), flagging HVAC upgrades and cool roof retrofits.

| Building | Address |
|----------|---------|
| Chase Tower | `201 N Central Ave, Phoenix, AZ 85004` |
| Frost Bank Tower | `401 Congress Ave, Austin, TX 78701` |
| Bank of America Plaza | `901 Main St, Dallas, TX 75202` |

> **Expected:** High heat sub-scores (60–90), 80+ projected extreme heat days, high cooling degree days.

### 🔥 High Wildfire Proximity Risk (California / Colorado)

Corporate campuses in suburban or wildland-urban interface (WUI) areas face significant wildfire risks.

| Building | Address |
|----------|---------|
| Medtronic Campus | `3576 Unocal Pl, Santa Rosa, CA 95403` |
| Oracle Campus | `500 Oracle Pkwy, Redwood City, CA 94065` |
| Lockheed Martin Space | `12257 S Wadsworth Blvd, Littleton, CO 80125` |

> **Expected:** Non-zero burn probability, wildfire sub-scores 20–60+ for WUI-adjacent properties.

<details>
<summary><b>📋 All 13 addresses (copy-paste ready for batch scoring)</b></summary>

```
701 Poydras St, New Orleans, LA 70139
1100 Louisiana Street, Houston, TX 77002
600 Brickell Ave, Miami, FL 33131
101 Seaport Blvd, Boston, MA 02210
415 Mission Street, San Francisco, CA 94105
333 S Hope St, Los Angeles, CA 90071
701 5th Ave, Seattle, WA 98104
201 N Central Ave, Phoenix, AZ 85004
401 Congress Ave, Austin, TX 78701
901 Main St, Dallas, TX 75202
3576 Unocal Pl, Santa Rosa, CA 95403
500 Oracle Pkwy, Redwood City, CA 94065
12257 S Wadsworth Blvd, Littleton, CO 80125
```

</details>

---

## 📄 License

Built for the JLL 2026 Hackathon. Internal use.
