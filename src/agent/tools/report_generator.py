"""
Report Generator — renders sustainability strategy into HTML and PDF reports.
"""

import logging
import os
from datetime import datetime
from typing import Optional

from jinja2 import Template

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML Report Template
# ---------------------------------------------------------------------------

REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, sans-serif;
            color: #1a1a2e;
            line-height: 1.6;
            font-size: 11pt;
        }
        .page { page-break-after: always; padding: 40px; }
        .page:last-child { page-break-after: avoid; }

        /* Cover */
        .cover {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 90vh;
            text-align: center;
            background: linear-gradient(135deg, #0a1628 0%, #1a3a5c 50%, #2d6a4f 100%);
            color: white;
            padding: 60px;
        }
        .cover h1 { font-size: 36pt; font-weight: 700; margin-bottom: 16px; }
        .cover h2 { font-size: 16pt; font-weight: 300; opacity: 0.9; margin-bottom: 40px; }
        .cover .meta { font-size: 10pt; opacity: 0.7; }

        /* Section headers */
        h2 { color: #1a3a5c; font-size: 18pt; border-bottom: 3px solid #2d6a4f; padding-bottom: 8px; margin: 30px 0 20px; }
        h3 { color: #2d6a4f; font-size: 13pt; margin: 20px 0 10px; }

        /* Tables */
        table { width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 10pt; }
        th { background: #1a3a5c; color: white; padding: 10px 12px; text-align: left; font-weight: 600; }
        td { padding: 8px 12px; border-bottom: 1px solid #e0e0e0; }
        tr:nth-child(even) td { background: #f8f9fa; }

        /* Risk badge */
        .risk-high { color: #d32f2f; font-weight: 600; }
        .risk-medium { color: #f57c00; font-weight: 600; }
        .risk-low { color: #388e3c; font-weight: 600; }

        /* Priority badges */
        .priority-quick { background: #e8f5e9; color: #2e7d32; padding: 2px 8px; border-radius: 12px; font-size: 9pt; }
        .priority-medium { background: #fff3e0; color: #e65100; padding: 2px 8px; border-radius: 12px; font-size: 9pt; }
        .priority-capex { background: #fce4ec; color: #c62828; padding: 2px 8px; border-radius: 12px; font-size: 9pt; }

        /* Key metrics */
        .metrics { display: flex; gap: 20px; margin: 20px 0; }
        .metric-card {
            flex: 1; background: #f0f7f4; border-left: 4px solid #2d6a4f;
            padding: 15px; border-radius: 4px;
        }
        .metric-card .value { font-size: 24pt; font-weight: 700; color: #1a3a5c; }
        .metric-card .label { font-size: 9pt; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }

        /* Narrative */
        .narrative { background: #fafafa; padding: 20px; border-radius: 8px; margin: 15px 0; border: 1px solid #e0e0e0; }
        .narrative p { margin-bottom: 12px; }

        /* Footer */
        .footer { text-align: center; font-size: 8pt; color: #999; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e0e0e0; }
    </style>
</head>
<body>

<!-- Cover Page -->
<div class="page cover">
    <h1>{{ title }}</h1>
    <h2>{{ subtitle }}</h2>
    <div class="meta">
        <p>Prepared by ClimateNexus AI</p>
        <p>{{ date }}</p>
        <p>{{ property_count }} Properties Analyzed</p>
    </div>
</div>

<!-- Executive Summary -->
<div class="page">
    <h2>1. Executive Summary</h2>

    <div class="metrics">
        <div class="metric-card">
            <div class="value">{{ portfolio_summary.avg_composite_score }}</div>
            <div class="label">Avg Risk Score</div>
        </div>
        <div class="metric-card">
            <div class="value">${{ "{:,.0f}".format(portfolio_summary.total_expected_annual_loss_usd) }}</div>
            <div class="label">Total Annual Risk Exposure</div>
        </div>
        <div class="metric-card">
            <div class="value">${{ "{:,.0f}".format(total_incentives) }}</div>
            <div class="label">Available Incentives</div>
        </div>
        <div class="metric-card">
            <div class="value">${{ "{:,.0f}".format(total_savings) }}</div>
            <div class="label">Est. Annual Savings</div>
        </div>
    </div>

    <div class="narrative">
        {{ strategy_narrative }}
    </div>

    <h3>Portfolio Risk Distribution</h3>
    <table>
        <tr>
            <th>Risk Level</th>
            <th>Properties</th>
            <th>Percentage</th>
        </tr>
        <tr>
            <td><span class="risk-high">High Risk (≥70)</span></td>
            <td>{{ portfolio_summary.high_risk_count }}</td>
            <td>{{ "{:.0f}".format(portfolio_summary.high_risk_count / property_count * 100 if property_count else 0) }}%</td>
        </tr>
        <tr>
            <td><span class="risk-medium">Medium Risk (40–69)</span></td>
            <td>{{ portfolio_summary.medium_risk_count }}</td>
            <td>{{ "{:.0f}".format(portfolio_summary.medium_risk_count / property_count * 100 if property_count else 0) }}%</td>
        </tr>
        <tr>
            <td><span class="risk-low">Low Risk (&lt;40)</span></td>
            <td>{{ portfolio_summary.low_risk_count }}</td>
            <td>{{ "{:.0f}".format(portfolio_summary.low_risk_count / property_count * 100 if property_count else 0) }}%</td>
        </tr>
    </table>
</div>

<!-- Recommended Actions -->
<div class="page">
    <h2>2. Recommended Actions</h2>

    {% for rec in recommendations %}
    <h3>{{ loop.index }}. {{ rec.action }}</h3>
    <table>
        <tr><td style="width:200px"><strong>Category</strong></td><td>{{ rec.category }}</td></tr>
        <tr><td><strong>Priority</strong></td><td>
            {% if rec.priority == "quick_win" %}<span class="priority-quick">Quick Win</span>
            {% elif rec.priority == "medium_term" %}<span class="priority-medium">Medium Term</span>
            {% else %}<span class="priority-capex">Capital Investment</span>{% endif %}
        </td></tr>
        <tr><td><strong>Affected Properties</strong></td><td>{{ rec.affected_properties | join(", ") }}</td></tr>
        <tr><td><strong>Estimated Cost</strong></td><td>${{ "{:,.0f}".format(rec.estimated_cost_usd) }}</td></tr>
        <tr><td><strong>Annual Savings</strong></td><td>${{ "{:,.0f}".format(rec.estimated_annual_savings_usd) }}</td></tr>
        {% if rec.payback_years %}<tr><td><strong>Payback Period</strong></td><td>{{ rec.payback_years }} years</td></tr>{% endif %}
        {% if rec.applicable_incentives %}<tr><td><strong>Applicable Incentives</strong></td><td>{{ rec.applicable_incentives | join("; ") }}</td></tr>{% endif %}
        <tr><td><strong>Rationale</strong></td><td>{{ rec.rationale }}</td></tr>
    </table>
    {% endfor %}
</div>

<!-- Financial Summary -->
<div class="page">
    <h2>3. Financial Summary</h2>

    <h3>Investment Overview</h3>
    <table>
        <tr><th>Measure</th><th>Cost</th><th>Annual Savings</th><th>Payback</th></tr>
        {% for rec in recommendations %}
        <tr>
            <td>{{ rec.action }}</td>
            <td>${{ "{:,.0f}".format(rec.estimated_cost_usd) }}</td>
            <td>${{ "{:,.0f}".format(rec.estimated_annual_savings_usd) }}</td>
            <td>{% if rec.payback_years %}{{ rec.payback_years }} yrs{% else %}N/A (risk avoidance){% endif %}</td>
        </tr>
        {% endfor %}
        <tr style="font-weight:700; background:#f0f7f4;">
            <td>TOTAL</td>
            <td>${{ "{:,.0f}".format(recommendations | sum(attribute='estimated_cost_usd')) }}</td>
            <td>${{ "{:,.0f}".format(recommendations | sum(attribute='estimated_annual_savings_usd')) }}</td>
            <td>—</td>
        </tr>
    </table>

    <h3>Available Incentives &amp; Tax Credits</h3>
    <div class="narrative">
        <p>Total estimated incentive value: <strong>${{ "{:,.0f}".format(total_incentives) }}</strong></p>
        <p>Net investment after incentives: <strong>${{ "{:,.0f}".format(recommendations | sum(attribute='estimated_cost_usd') - total_incentives) }}</strong></p>
    </div>
</div>

<!-- Risk Heatmap -->
<div class="page">
    <h2>4. Risk Heatmap</h2>

    <h3>Properties by Hazard Category</h3>
    <table>
        <tr>
            <th>Property</th>
            <th>Composite Score</th>
            <th>Flood</th>
            <th>Heat</th>
            <th>Wildfire</th>
            <th>Transition</th>
            <th>Seismic</th>
        </tr>
        {% for prop in risk_details %}
        <tr>
            <td>{{ prop.address }}</td>
            <td>
                {% if prop.composite_score >= 70 %}<span class="risk-high">{{ prop.composite_score }}</span>
                {% elif prop.composite_score >= 40 %}<span class="risk-medium">{{ prop.composite_score }}</span>
                {% else %}<span class="risk-low">{{ prop.composite_score }}</span>{% endif %}
            </td>
            {% for hazard in ["flood", "heat", "wildfire", "transition", "seismic"] %}
            <td>
                {% set score = prop.sub_scores.get(hazard, 0) if prop.sub_scores else 0 %}
                {% if score >= 70 %}<span class="risk-high">{{ score }}</span>
                {% elif score >= 40 %}<span class="risk-medium">{{ score }}</span>
                {% else %}<span class="risk-low">{{ score }}</span>{% endif %}
            </td>
            {% endfor %}
        </tr>
        {% endfor %}
    </table>

    <h3>Legend</h3>
    <table>
        <tr>
            <td><span class="risk-high">&#9632;</span> High Risk (&ge;70)</td>
            <td><span class="risk-medium">&#9632;</span> Medium Risk (40&ndash;69)</td>
            <td><span class="risk-low">&#9632;</span> Low Risk (&lt;40)</td>
        </tr>
    </table>
</div>

<!-- Regulatory Compliance Roadmap -->
<div class="page">
    <h2>5. Regulatory Compliance Roadmap</h2>

    {% if regulations %}
    {% for reg in regulations %}
    <h3>{{ reg.name }}</h3>
    <table>
        <tr><td style="width:200px"><strong>Jurisdiction</strong></td><td>{{ reg.jurisdiction }}</td></tr>
        <tr><td><strong>Affected Properties</strong></td><td>{{ reg.affected_properties | join(", ") }}</td></tr>
        <tr><td><strong>Key Requirement</strong></td><td>{{ reg.requirement }}</td></tr>
        <tr><td><strong>Deadline</strong></td><td>{{ reg.deadline }}</td></tr>
        <tr><td><strong>Penalty</strong></td><td>{{ reg.penalty }}</td></tr>
        <tr><td><strong>Recommended Pathway</strong></td><td>{{ reg.pathway }}</td></tr>
    </table>
    {% endfor %}
    {% else %}
    <div class="narrative">
        <p>No building performance regulations were identified for the properties in this portfolio. However, proactive energy efficiency improvements position assets for future compliance as regulations expand to additional jurisdictions.</p>
    </div>
    {% endif %}
</div>

<!-- Appendix -->
<div class="page">
    <h2>6. Appendix</h2>

    <h3>A. Methodology</h3>
    <div class="narrative">
        <p><strong>Risk Scoring:</strong> Multi-hazard composite risk scores (0&ndash;100) are calculated using a weighted ensemble model combining data from FEMA National Flood Hazard Layer, NOAA climate normals, USFS Wildfire Risk to Communities, USGS earthquake hazard data, and OpenStreetMap building metadata.</p>
        <p><strong>Financial Estimates:</strong> Retrofit costs and savings are based on industry benchmarks adjusted for building type, climate zone, and size. Payback periods use simple payback (cost / annual savings). NPV calculations use a 5% discount rate over a 10-year horizon.</p>
        <p><strong>Incentive Matching:</strong> Incentives are matched by property location (state/city) and planned measure type against a curated database of federal (IRA), state, and local programs. Estimated values are approximations; actual amounts depend on project details and application outcomes.</p>
        <p><strong>Strategy Generation:</strong> Recommendations are synthesized by an AI agent (LangGraph + Gemini) using retrieval-augmented generation over a curated knowledge base of sustainability regulations, technology specifications, and financial incentive programs.</p>
    </div>

    <h3>B. Data Sources</h3>
    <table>
        <tr><th>Source</th><th>Data Used</th></tr>
        <tr><td>FEMA NFHL</td><td>Flood zone designations, NRI loss values</td></tr>
        <tr><td>NOAA Climate Normals</td><td>Temperature and precipitation data for heat risk</td></tr>
        <tr><td>USFS</td><td>Wildfire risk ratings by geographic area</td></tr>
        <tr><td>USGS</td><td>Peak ground acceleration (seismic hazard)</td></tr>
        <tr><td>OpenStreetMap</td><td>Building type, levels, land use classification</td></tr>
        <tr><td>EPA ENERGY STAR</td><td>Building energy performance benchmarks</td></tr>
        <tr><td>IRA / DSIRE</td><td>Federal and state incentive programs</td></tr>
    </table>

    <h3>C. Disclaimer</h3>
    <div class="narrative">
        <p>This report is generated by ClimateNexus AI for informational and planning purposes only. All financial projections, risk scores, and incentive estimates are approximations based on publicly available data and industry benchmarks. They should not be construed as financial advice. Consult qualified professionals for engineering assessments, legal compliance review, and investment decisions.</p>
    </div>

    <div class="footer">
        <p>Generated by ClimateNexus AI &mdash; {{ date }}</p>
        <p>Confidential &mdash; Prepared for internal use</p>
    </div>
</div>

</body>
</html>"""


class ReportGenerator:
    """Renders sustainability strategy into HTML and PDF reports."""

    def __init__(self, output_dir: str = "./reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.template = Template(REPORT_TEMPLATE)

    def generate_html(
        self,
        strategy_data: dict,
        title: str = "ClimateNexus Sustainability Strategy",
    ) -> str:
        """Render strategy data into an HTML report string."""
        context = {
            "title": title,
            "subtitle": "Multi-Hazard Climate Risk Assessment & Sustainability Strategy",
            "date": datetime.now().strftime("%B %d, %Y"),
            "property_count": strategy_data.get("property_count", 0),
            "portfolio_summary": strategy_data.get("portfolio_summary", {}),
            "strategy_narrative": strategy_data.get("strategy_narrative", ""),
            "recommendations": strategy_data.get("recommendations", []),
            "total_incentives": strategy_data.get("total_incentives_usd", 0),
            "total_savings": strategy_data.get("total_savings_usd", 0),
            "risk_details": strategy_data.get("risk_details", []),
            "regulations": strategy_data.get("regulations", []),
        }
        return self.template.render(**context)

    def save_html(
        self,
        strategy_data: dict,
        filename: Optional[str] = None,
        title: str = "ClimateNexus Sustainability Strategy",
    ) -> str:
        """Render and save HTML report to disk. Returns file path."""
        html = self.generate_html(strategy_data, title)
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"strategy_report_{ts}.html"

        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info("HTML report saved to %s", filepath)
        return filepath

    def save_pdf(
        self,
        strategy_data: dict,
        filename: Optional[str] = None,
        title: str = "ClimateNexus Sustainability Strategy",
    ) -> str:
        """Render and save PDF report. Returns file path."""
        html = self.generate_html(strategy_data, title)
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"strategy_report_{ts}.pdf"

        filepath = os.path.join(self.output_dir, filename)

        try:
            from weasyprint import HTML
            HTML(string=html).write_pdf(filepath)
            logger.info("PDF report saved to %s", filepath)
        except Exception as exc:
            logger.warning("PDF generation failed (%s) — falling back to HTML", exc)
            filepath = filepath.replace(".pdf", ".html")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)

        return filepath
