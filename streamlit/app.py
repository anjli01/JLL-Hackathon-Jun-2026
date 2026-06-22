"""
ClimateNexus — Streamlit Frontend
Entry point for the multi-page Streamlit app.
"""

import streamlit as st
import requests

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="ClimateNexus",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

if "api_base" not in st.session_state:
    st.session_state.api_base = "http://127.0.0.1:8001"
if "scored_results" not in st.session_state:
    st.session_state.scored_results = None
if "strategy_response" not in st.session_state:
    st.session_state.strategy_response = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global */
    .stApp { font-family: 'Inter', sans-serif; }

    /* Hero section */
    .hero {
        background: linear-gradient(135deg, #0a1628 0%, #1a3a5c 50%, #2d6a4f 100%);
        padding: 60px 40px;
        border-radius: 16px;
        text-align: center;
        color: white;
        margin-bottom: 30px;
    }
    .hero h1 {
        font-size: 3rem;
        font-weight: 700;
        margin-bottom: 8px;
        letter-spacing: -0.5px;
    }
    .hero .tagline {
        font-size: 1.3rem;
        font-weight: 300;
        opacity: 0.9;
        margin-bottom: 20px;
    }
    .hero .subtitle {
        font-size: 0.95rem;
        opacity: 0.7;
    }

    /* Step cards */
    .step-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
        border: 1px solid #e0e0e0;
        height: 100%;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .step-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .step-card .step-num {
        background: linear-gradient(135deg, #1a3a5c, #2d6a4f);
        color: white;
        width: 36px; height: 36px;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        margin-bottom: 12px;
    }
    .step-card h3 { color: #1a3a5c; margin: 8px 0; font-size: 1.1rem; }
    .step-card p { color: #666; font-size: 0.9rem; margin: 0; }

    /* Status badge */
    .status-ok { color: #388e3c; font-weight: 600; }
    .status-err { color: #d32f2f; font-weight: 600; }

    /* Risk badges */
    .risk-high { background: #ffebee; color: #c62828; padding: 2px 10px; border-radius: 12px; font-weight: 600; font-size: 0.85rem; }
    .risk-medium { background: #fff3e0; color: #e65100; padding: 2px 10px; border-radius: 12px; font-weight: 600; font-size: 0.85rem; }
    .risk-low { background: #e8f5e9; color: #2e7d32; padding: 2px 10px; border-radius: 12px; font-weight: 600; font-size: 0.85rem; }

    /* Priority badges */
    .priority-quick { background: #e8f5e9; color: #2e7d32; padding: 3px 12px; border-radius: 12px; font-weight: 600; }
    .priority-medium { background: #fff3e0; color: #e65100; padding: 3px 12px; border-radius: 12px; font-weight: 600; }
    .priority-capex { background: #fce4ec; color: #c62828; padding: 3px 12px; border-radius: 12px; font-weight: 600; }

    /* Metric card override */
    div[data-testid="stMetric"] {
        background: #f0f7f4;
        border-left: 4px solid #2d6a4f;
        padding: 12px 16px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 🏢 **ClimateNexus**")
    st.caption("by JLL · 2026 Hackathon")
    st.markdown("---")
    st.markdown("### ⚙️ Settings")
    api_url = st.text_input("API Base URL", value=st.session_state.api_base)
    st.session_state.api_base = api_url

    # Health check
    try:
        r = requests.get(f"{api_url}/docs", timeout=3)
        st.markdown('<span class="status-ok">● Backend Connected</span>', unsafe_allow_html=True)
    except Exception:
        st.markdown('<span class="status-err">● Backend Offline</span>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(
        "**ClimateNexus** v1.0  \n"
        "JLL 2026 Hackathon  \n"
        "*Score the risk. Prescribe the cure.*"
    )

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------

st.markdown("""
<div class="hero">
    <h1>🏢 ClimateNexus</h1>
    <div class="tagline">Score the risk. Prescribe the cure.</div>
    <div class="subtitle">
        AI-powered climate risk scoring & sustainability strategy generation<br>
        for commercial real estate portfolios
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# How it works — 4 steps
# ---------------------------------------------------------------------------

st.markdown("### How It Works")

cols = st.columns(4)
steps = [
    ("1", "🗺️ Score", "Upload a portfolio of addresses and score each property for multi-hazard climate risk"),
    ("2", "📊 Strategize", "AI agent generates tailored sustainability strategy with ROI-ranked recommendations"),
    ("3", "💬 Refine", "Chat with the agent to customize the strategy for your client's needs"),
    ("4", "📑 Deliver", "Download a branded, client-ready strategy deck in PDF or HTML"),
]

for col, (num, title, desc) in zip(cols, steps):
    with col:
        st.markdown(f"""
        <div class="step-card">
            <div class="step-num">{num}</div>
            <h3>{title}</h3>
            <p>{desc}</p>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Quick stats from session
# ---------------------------------------------------------------------------

if st.session_state.scored_results:
    data = st.session_state.scored_results
    ps = data["portfolio_summary"]
    st.markdown("### 📋 Current Portfolio")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Properties Scored", ps["total_properties"])
    c2.metric("Avg Risk Score", f"{ps['avg_composite_score']:.0f}")
    c3.metric("High Risk", ps["high_risk_count"])
    c4.metric("Total Annual Risk", f"${ps['total_expected_annual_loss_usd']:,.0f}")
    st.info("👈 Navigate to **Strategy Agent** to generate recommendations, or **Portfolio Scorer** to score more properties.")
else:
    st.info("👈 Start by navigating to **Portfolio Scorer** in the sidebar to score your first properties.")
