"""
Page 1: Portfolio Scorer
CSV upload + single/batch scoring + interactive map + risk heatmap table
"""

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Portfolio Scorer — ClimateNexus", page_icon="🗺️", layout="wide")

API = st.session_state.get("api_base", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# Custom CSS (shared styles)
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
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown("# 🗺️ Portfolio Scorer")
st.markdown("Upload a portfolio of properties and score each one for multi-hazard climate risk.")
st.markdown("---")

# ---------------------------------------------------------------------------
# Input section — 3 tabs
# ---------------------------------------------------------------------------

tab_single, tab_batch, tab_csv = st.tabs(["🏠 Single Address", "📋 Batch Addresses", "📁 CSV Upload"])

scored = None

with tab_single:
    address = st.text_input(
        "Property address",
        placeholder="e.g. 830 Brickell Plaza, Miami, FL 33131",
    )
    if st.button("Score Property", key="btn_single", type="primary"):
        if not address.strip():
            st.warning("Please enter an address.")
        else:
            with st.spinner(f"Scoring {address}…"):
                try:
                    r = requests.post(f"{API}/score", json={"address": address}, timeout=120)
                    r.raise_for_status()
                    single = r.json()
                    # Wrap in batch format for consistent rendering
                    scored = {
                        "results": [single],
                        "portfolio_summary": {
                            "total_properties": 1,
                            "avg_composite_score": single["composite_score"],
                            "max_composite_score": single["composite_score"],
                            "min_composite_score": single["composite_score"],
                            "high_risk_count": 1 if single["composite_score"] >= 70 else 0,
                            "medium_risk_count": 1 if 40 <= single["composite_score"] < 70 else 0,
                            "low_risk_count": 1 if single["composite_score"] < 40 else 0,
                            "total_expected_annual_loss_usd": single["expected_annual_loss_usd"],
                            "top_hazards": {},
                        },
                        "errors": [],
                    }
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot connect to backend. Is the API running?")
                except Exception as e:
                    st.error(f"❌ Scoring failed: {e}")

with tab_batch:
    batch_text = st.text_area(
        "Enter addresses (one per line)",
        height=150,
        placeholder="830 Brickell Plaza, Miami, FL 33131\n55 Water Street, New York, NY 10041\n233 S Wacker Dr, Chicago, IL 60606",
    )
    if st.button("Score All", key="btn_batch", type="primary"):
        addresses = [a.strip() for a in batch_text.strip().split("\n") if a.strip()]
        if not addresses:
            st.warning("Please enter at least one address.")
        else:
            with st.spinner(f"Scoring {len(addresses)} properties…"):
                try:
                    r = requests.post(
                        f"{API}/score/batch",
                        json={"addresses": addresses},
                        timeout=300,
                    )
                    r.raise_for_status()
                    scored = r.json()
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot connect to backend. Is the API running?")
                except Exception as e:
                    st.error(f"❌ Scoring failed: {e}")

with tab_csv:
    uploaded = st.file_uploader("Upload CSV with 'address' column", type=["csv"])
    if uploaded and st.button("Upload & Score", key="btn_csv", type="primary"):
        with st.spinner("Uploading and scoring…"):
            try:
                files = {"file": (uploaded.name, uploaded.getvalue(), "text/csv")}
                r = requests.post(f"{API}/score/upload-csv", files=files, timeout=300)
                r.raise_for_status()
                scored = r.json()
            except requests.exceptions.ConnectionError:
                st.error("❌ Cannot connect to backend. Is the API running?")
            except Exception as e:
                st.error(f"❌ Scoring failed: {e}")

# ---------------------------------------------------------------------------
# Save to session state
# ---------------------------------------------------------------------------

if scored:
    st.session_state.scored_results = scored

# Use whatever is in session state
data = st.session_state.get("scored_results")

if not data:
    st.info("👆 Score some properties above to see results.")
    st.stop()

# ---------------------------------------------------------------------------
# Results rendering
# ---------------------------------------------------------------------------

results = data["results"]
ps = data["portfolio_summary"]
errors = data.get("errors", [])

st.markdown("---")
st.markdown("## 📊 Portfolio Summary")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Properties Scored", ps["total_properties"])
c2.metric("Avg Risk Score", f"{ps['avg_composite_score']:.0f} / 100")
c3.metric("High Risk Properties", ps["high_risk_count"])
c4.metric("Annual Risk Exposure", f"${ps['total_expected_annual_loss_usd']:,.0f}")

if errors:
    with st.expander(f"⚠️ {len(errors)} addresses failed", expanded=False):
        for err in errors:
            st.warning(f"**{err['address']}**: {err['error']}")

# ---------------------------------------------------------------------------
# Map (Folium)
# ---------------------------------------------------------------------------

st.markdown("## 🗺️ Risk Map")

m = folium.Map(location=[37.0, -95.7], zoom_start=4, tiles="CartoDB positron")

for prop in results:
    score = prop["composite_score"]
    if score >= 70:
        color = "red"
        icon_color = "white"
    elif score >= 40:
        color = "orange"
        icon_color = "white"
    else:
        color = "green"
        icon_color = "white"

    # Find top hazard
    sub = prop["sub_scores"]
    top_hazard = max(sub, key=lambda k: sub[k])

    popup_html = f"""
    <div style="font-family: Inter, sans-serif; min-width: 200px;">
        <strong>{prop['address']}</strong><br>
        <hr style="margin:4px 0">
        <b>Composite Score:</b> {score:.0f}/100<br>
        <b>Top Hazard:</b> {top_hazard.title()} ({sub[top_hazard]:.0f})<br>
        <b>Annual Risk:</b> ${prop['expected_annual_loss_usd']:,.0f}<br>
        <hr style="margin:4px 0">
        Flood: {sub['flood']:.0f} | Heat: {sub['heat']:.0f} | Wildfire: {sub['wildfire']:.0f}<br>
        Transition: {sub['transition']:.0f} | Seismic: {sub['seismic']:.0f}
    </div>
    """

    folium.Marker(
        location=[prop["latitude"], prop["longitude"]],
        popup=folium.Popup(popup_html, max_width=300),
        tooltip=f"{prop['address'][:30]}… ({score:.0f})",
        icon=folium.Icon(color=color, icon_color=icon_color, icon="info-sign"),
    ).add_to(m)

# Auto-fit bounds
if len(results) > 1:
    bounds = [[p["latitude"], p["longitude"]] for p in results]
    m.fit_bounds(bounds, padding=(30, 30))
elif results:
    m.location = [results[0]["latitude"], results[0]["longitude"]]
    m.zoom_start = 13

st_folium(m, width=None, height=480, use_container_width=True)

# ---------------------------------------------------------------------------
# Risk Heatmap Table
# ---------------------------------------------------------------------------

st.markdown("## 📋 Risk Heatmap")

rows = []
for prop in results:
    sub = prop["sub_scores"]
    rows.append({
        "Address": prop["address"],
        "Composite": prop["composite_score"],
        "Flood": sub["flood"],
        "Heat": sub["heat"],
        "Wildfire": sub["wildfire"],
        "Transition": sub["transition"],
        "Seismic": sub["seismic"],
        "EAL ($)": prop["expected_annual_loss_usd"],
    })

df = pd.DataFrame(rows)


def _color_risk(val):
    """Apply background color based on risk level."""
    if isinstance(val, (int, float)):
        if val >= 70:
            return "background-color: #ffcdd2; color: #b71c1c;"
        elif val >= 40:
            return "background-color: #ffe0b2; color: #e65100;"
        elif val > 0:
            return "background-color: #c8e6c9; color: #1b5e20;"
    return ""


score_cols = ["Composite", "Flood", "Heat", "Wildfire", "Transition", "Seismic"]
styled = df.style.map(_color_risk, subset=score_cols).format(
    {"EAL ($)": "${:,.0f}", "Composite": "{:.0f}", "Flood": "{:.0f}",
     "Heat": "{:.0f}", "Wildfire": "{:.0f}", "Transition": "{:.0f}", "Seismic": "{:.0f}"}
)

st.dataframe(styled, use_container_width=True, height=min(400, 60 + len(rows) * 35))

# ---------------------------------------------------------------------------
# Per-property Score Cards (expandable)
# ---------------------------------------------------------------------------

st.markdown("## 🏢 Property Score Cards")

for prop in results:
    score = prop["composite_score"]
    badge = "risk-high" if score >= 70 else ("risk-medium" if score >= 40 else "risk-low")
    level = "High" if score >= 70 else ("Medium" if score >= 40 else "Low")

    with st.expander(f"**{prop['address']}** — {score:.0f}/100 ({level} Risk)"):
        col_radar, col_shap = st.columns(2)

        sub = prop["sub_scores"]

        # Radar chart
        with col_radar:
            categories = list(sub.keys())
            values = [sub[k] for k in categories]

            fig_radar = go.Figure(data=go.Scatterpolar(
                r=values + [values[0]],
                theta=[c.title() for c in categories] + [categories[0].title()],
                fill="toself",
                fillcolor="rgba(45, 106, 79, 0.2)",
                line=dict(color="#2d6a4f", width=2),
            ))
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10)),
                ),
                title="Sub-Score Radar",
                height=350,
                margin=dict(t=40, b=20, l=40, r=40),
                font=dict(family="Inter"),
            )
            st.plotly_chart(fig_radar, use_container_width=True)

        # SHAP waterfall
        with col_shap:
            shap = prop.get("shap_explanations", {})
            base = shap.pop("base_value", 35)
            shap_items = sorted(shap.items(), key=lambda x: abs(x[1]), reverse=True)

            if shap_items:
                labels = [k.replace("_impact", "").replace("_", " ").title() for k, _ in shap_items]
                vals = [v for _, v in shap_items]
                colors = ["#c62828" if v > 0 else "#2e7d32" for v in vals]

                fig_shap = go.Figure(go.Bar(
                    x=vals,
                    y=labels,
                    orientation="h",
                    marker_color=colors,
                    text=[f"+{v:.1f}" if v > 0 else f"{v:.1f}" for v in vals],
                    textposition="outside",
                ))
                fig_shap.update_layout(
                    title=f"SHAP Explainability (base: {base:.0f})",
                    xaxis_title="Impact on Score",
                    height=350,
                    margin=dict(t=40, b=20, l=100, r=40),
                    font=dict(family="Inter"),
                )
                st.plotly_chart(fig_shap, use_container_width=True)

        # Raw features (using checkbox instead of nested expander)
        if st.checkbox("📄 Show Raw Features JSON", key=f"raw_{prop['address']}"):
            st.json(prop.get("raw_features", {}))
