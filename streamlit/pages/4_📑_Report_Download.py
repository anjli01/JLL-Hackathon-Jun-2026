"""
Page 4: Report Download
Generate and download client-ready strategy reports in HTML/PDF.
"""

import streamlit as st
import streamlit.components.v1 as components
import requests

st.set_page_config(page_title="Report Download — ClimateNexus", page_icon="📑", layout="wide")

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
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown("# 📑 Report Download")
st.markdown("Generate a branded, client-ready strategy deck for your meeting.")
st.markdown("---")

# ---------------------------------------------------------------------------
# Check prereqs
# ---------------------------------------------------------------------------

strategy = st.session_state.get("strategy_response")
if not strategy:
    st.warning("⚠️ No strategy generated yet. Please generate a strategy first.")
    st.page_link("pages/2_📊_Strategy_Agent.py", label="Go to Strategy Agent →", icon="📊")
    st.stop()

# ---------------------------------------------------------------------------
# Report options
# ---------------------------------------------------------------------------

st.markdown("### ⚙️ Report Options")

col1, col2 = st.columns(2)

with col1:
    report_title = st.text_input(
        "Report Title",
        value="ClimateNexus Sustainability Strategy",
        help="This title appears on the cover page of the report.",
    )

with col2:
    st.markdown("**Included Sections:**")
    st.markdown(
        "✅ Executive Summary  \n"
        "✅ Recommended Actions  \n"
        "✅ Financial Summary  \n"
        "✅ Risk Heatmap  \n"
        "✅ Regulatory Compliance Roadmap  \n"
        "✅ Appendix (Methodology, Data Sources)"
    )

# Show summary of what will be in the report
recs = strategy.get("recommendations", [])
st.markdown("---")
st.markdown("### 📋 Report Preview")

c1, c2, c3 = st.columns(3)
c1.metric("Recommendations", len(recs))
c2.metric("Properties", strategy.get("portfolio_summary", {}).get("total_properties", 0))
c3.metric("Regulations Matched", len(strategy.get("regulations", [])))

# ---------------------------------------------------------------------------
# Generate button
# ---------------------------------------------------------------------------

st.markdown("---")

generate_btn = st.button(
    "📑 Generate Report",
    type="primary",
    use_container_width=True,
)

if generate_btn:
    # Build the strategy data dict for the report endpoint
    strategy_data = {
        "property_count": strategy.get("portfolio_summary", {}).get("total_properties", 0),
        "portfolio_summary": strategy.get("portfolio_summary", {}),
        "strategy_narrative": strategy.get("strategy_narrative", ""),
        "recommendations": strategy.get("recommendations", []),
        "total_incentives_usd": strategy.get("total_incentives_usd", 0),
        "total_savings_usd": strategy.get("total_savings_usd", 0),
        "risk_details": strategy.get("risk_details", []),
        "regulations": strategy.get("regulations", []),
    }

    with st.spinner("📝 Generating report…"):
        try:
            r = requests.post(
                f"{API}/agent/report",
                json={
                    "strategy": strategy_data,
                    "report_title": report_title,
                },
                timeout=120,
            )
            r.raise_for_status()

            content_type = r.headers.get("content-type", "")

            if "text/html" in content_type:
                html_content = r.text
                st.session_state.report_html = html_content
                st.session_state.report_format = "html"
                st.success("✅ Report generated!")
            elif "application/pdf" in content_type:
                st.session_state.report_pdf = r.content
                st.session_state.report_format = "pdf"
                st.success("✅ PDF report generated!")
            else:
                # Try to parse as JSON (FileResponse path)
                data = r.json()
                report_path = data.get("report_path", "")
                if report_path:
                    # Fetch the actual file
                    file_r = requests.get(
                        f"{API}/agent/report/download",
                        params={"path": report_path},
                        timeout=30,
                    )
                    if file_r.ok:
                        if report_path.endswith(".pdf"):
                            st.session_state.report_pdf = file_r.content
                            st.session_state.report_format = "pdf"
                        else:
                            st.session_state.report_html = file_r.text
                            st.session_state.report_format = "html"
                        st.success("✅ Report generated!")
                    else:
                        st.error("Failed to fetch generated report file.")

        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend. Is the API running?")
        except Exception as e:
            st.error(f"❌ Report generation failed: {e}")

# ---------------------------------------------------------------------------
# Display report
# ---------------------------------------------------------------------------

report_format = st.session_state.get("report_format")

if report_format == "html" and st.session_state.get("report_html"):
    html_content = st.session_state.report_html

    st.markdown("### 👁️ Report Preview")
    components.html(html_content, height=800, scrolling=True)

    st.markdown("---")

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            label="📥 Download HTML Report",
            data=html_content,
            file_name="ClimateNexus_Strategy_Report.html",
            mime="text/html",
            use_container_width=True,
            type="primary",
        )
    with col_dl2:
        st.info("💡 Open the HTML file in a browser and use **Print → Save as PDF** for a polished PDF version.")

elif report_format == "pdf" and st.session_state.get("report_pdf"):
    pdf_data = st.session_state.report_pdf

    st.markdown("### 📄 PDF Report Ready")
    st.download_button(
        label="📥 Download PDF Report",
        data=pdf_data,
        file_name="ClimateNexus_Strategy_Report.pdf",
        mime="application/pdf",
        use_container_width=True,
        type="primary",
    )
