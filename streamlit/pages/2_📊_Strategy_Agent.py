"""
Page 2: Strategy Agent
Generate sustainability strategy from scored portfolio.
"""

import streamlit as st
import requests
import plotly.graph_objects as go

st.set_page_config(page_title="Strategy Agent — ClimateNexus", page_icon="📊", layout="wide")

API = st.session_state.get("api_base", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    .stApp { font-family: 'Inter', sans-serif; }
    div[data-testid="stMetric"] {
        background: #f0f7f4;
        border-left: 4px solid #2d6a4f;
        padding: 12px 16px;
        border-radius: 8px;
    }
    .rec-card {
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 12px;
        border-left: 5px solid;
    }
    .rec-quick { background: #f1f8e9; border-color: #43a047; }
    .rec-medium { background: #fff8e1; border-color: #fb8c00; }
    .rec-capex { background: #fce4ec; border-color: #e53935; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown("# 📊 Strategy Agent")
st.markdown("Generate a tailored sustainability strategy based on your scored portfolio.")
st.markdown("---")

# ---------------------------------------------------------------------------
# Check prereqs
# ---------------------------------------------------------------------------

scored = st.session_state.get("scored_results")
if not scored:
    st.warning("⚠️ No scored properties found. Please score your portfolio first.")
    st.page_link("pages/1_🗺️_Portfolio_Scorer.py", label="Go to Portfolio Scorer →", icon="🗺️")
    st.stop()

results = scored["results"]

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

st.markdown("### Select Properties")
addresses = [r["address"] for r in results]
selected = st.multiselect(
    "Properties to include in strategy",
    options=addresses,
    default=addresses,
)

if not selected:
    st.warning("Please select at least one property.")
    st.stop()

user_context = st.text_area(
    "📝 Broker Notes (optional)",
    placeholder="e.g. Focus on LL97 compliance for NYC properties, client interested in LEED certification",
    height=80,
)

generate_btn = st.button("🚀 Generate Strategy", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

if generate_btn:
    with st.spinner("🤖 AI agent is analyzing risks and generating strategy… This may take 30–60 seconds."):
        try:
            r = requests.post(
                f"{API}/agent/strategize",
                json={"addresses": selected, "user_context": user_context},
                timeout=300,
            )
            r.raise_for_status()
            st.session_state.strategy_response = r.json()
            st.success("✅ Strategy generated!")
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend. Is the API running?")
        except Exception as e:
            st.error(f"❌ Strategy generation failed: {e}")

# ---------------------------------------------------------------------------
# Render strategy
# ---------------------------------------------------------------------------

strategy = st.session_state.get("strategy_response")
if not strategy:
    st.info("👆 Click **Generate Strategy** to create recommendations for your portfolio.")
    st.stop()

st.markdown("---")

# ---------------------------------------------------------------------------
# Financial summary
# ---------------------------------------------------------------------------

st.markdown("## 💰 Financial Summary")

recs = strategy.get("recommendations", [])
total_cost = sum(r["estimated_cost_usd"] for r in recs)
total_savings = strategy.get("total_savings_usd", 0)
total_incentives = strategy.get("total_incentives_usd", 0)
avg_payback = 0
payback_recs = [r for r in recs if r.get("payback_years")]
if payback_recs:
    avg_payback = sum(r["payback_years"] for r in payback_recs) / len(payback_recs)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Annual Savings", f"${total_savings:,.0f}")
c2.metric("Available Incentives", f"${total_incentives:,.0f}")
c3.metric("Total Investment", f"${total_cost:,.0f}")
c4.metric("Avg Payback", f"{avg_payback:.1f} years" if avg_payback else "N/A")

# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

st.markdown("## 📋 Recommendations")

priority_order = {"quick_win": 0, "medium_term": 1, "capex_heavy": 2}
sorted_recs = sorted(recs, key=lambda r: priority_order.get(r["priority"], 9))

priority_labels = {
    "quick_win": ("🟢 Quick Win", "rec-quick"),
    "medium_term": ("🟡 Medium Term", "rec-medium"),
    "capex_heavy": ("🔴 Capital Investment", "rec-capex"),
}

for i, rec in enumerate(sorted_recs, 1):
    label, css_class = priority_labels.get(rec["priority"], ("⚪ Other", "rec-quick"))

    with st.container():
        st.markdown(f"""
        <div class="rec-card {css_class}">
            <strong>{i}. {rec['action']}</strong> &nbsp; <small>{label}</small><br>
            <table style="width:100%; margin-top:8px; font-size:0.9rem;">
                <tr>
                    <td>💲 <b>Cost:</b> ${rec['estimated_cost_usd']:,.0f}</td>
                    <td>💰 <b>Savings/yr:</b> ${rec['estimated_annual_savings_usd']:,.0f}</td>
                    <td>⏱️ <b>Payback:</b> {f"{rec['payback_years']:.1f} yrs" if rec.get('payback_years') else "N/A"}</td>
                </tr>
                <tr>
                    <td colspan="2">🏢 <b>Properties:</b> {', '.join(rec.get('affected_properties', []))}</td>
                    <td>🏷️ <b>Incentives:</b> {', '.join(rec.get('applicable_incentives', [])) or 'None'}</td>
                </tr>
            </table>
            <p style="margin-top:8px; color:#555; font-size:0.85rem;">{rec.get('rationale', '')}</p>
        </div>
        """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Investment breakdown chart
# ---------------------------------------------------------------------------

st.markdown("## 📈 Investment Breakdown")

col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    # Cost by category
    categories = {}
    for rec in recs:
        cat = rec.get("category", "other").replace("_", " ").title()
        categories[cat] = categories.get(cat, 0) + rec["estimated_cost_usd"]

    fig_pie = go.Figure(data=[go.Pie(
        labels=list(categories.keys()),
        values=list(categories.values()),
        hole=0.4,
        textinfo="label+percent",
        marker=dict(colors=["#1a3a5c", "#2d6a4f", "#f57c00", "#d32f2f", "#5c6bc0", "#00897b"]),
    )])
    fig_pie.update_layout(
        title="Investment by Category",
        height=350,
        font=dict(family="Inter"),
        margin=dict(t=40, b=20),
    )
    st.plotly_chart(fig_pie, use_container_width=True)

with col_chart2:
    # Cost vs savings bar chart
    actions = [r["action"][:25] for r in sorted_recs]
    costs = [r["estimated_cost_usd"] for r in sorted_recs]
    savings = [r["estimated_annual_savings_usd"] * 10 for r in sorted_recs]  # 10yr savings

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(name="Investment", x=actions, y=costs, marker_color="#1a3a5c"))
    fig_bar.add_trace(go.Bar(name="10yr Savings", x=actions, y=savings, marker_color="#2d6a4f"))
    fig_bar.update_layout(
        title="Investment vs 10-Year Savings",
        barmode="group",
        height=350,
        font=dict(family="Inter"),
        margin=dict(t=40, b=20),
        xaxis_tickangle=-30,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# ---------------------------------------------------------------------------
# Strategy narrative
# ---------------------------------------------------------------------------

st.markdown("## 📝 Strategy Narrative")
with st.expander("View full AI-generated narrative", expanded=True):
    narrative = strategy.get("strategy_narrative", "")
    if narrative.strip().startswith("<"):
        st.markdown(narrative, unsafe_allow_html=True)
    else:
        st.markdown(narrative)

# ---------------------------------------------------------------------------
# Regulatory compliance
# ---------------------------------------------------------------------------

regulations = strategy.get("regulations", [])
if regulations:
    st.markdown("## ⚖️ Regulatory Compliance")
    for reg in regulations:
        with st.expander(f"**{reg['name']}** — {reg['jurisdiction']}"):
            c1, c2 = st.columns(2)
            c1.markdown(f"**Requirement:** {reg.get('requirement', 'N/A')}")
            c1.markdown(f"**Deadline:** {reg.get('deadline', 'N/A')}")
            c2.markdown(f"**Penalty:** {reg.get('penalty', 'N/A')}")
            c2.markdown(f"**Pathway:** {reg.get('pathway', 'N/A')}")
            st.markdown(f"**Affected Properties:** {', '.join(reg.get('affected_properties', []))}")

# ---------------------------------------------------------------------------
# Next step
# ---------------------------------------------------------------------------

st.markdown("---")
st.info("💬 Navigate to **Chat Refinement** to ask follow-up questions, or **Report Download** to generate a PDF.")
