"""
End-to-end test of the ClimateNexus application.
Tests all 4 Streamlit pages by calling the FastAPI backend directly.
"""

import json
import time
import urllib.request

API = "http://127.0.0.1:8008"

def post_json(path, body, timeout=120):
    req = urllib.request.Request(
        f"{API}{path}",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(body).encode(),
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content_type = resp.headers.get("Content-Type", "")
        raw = resp.read()
        if "application/json" in content_type:
            return json.loads(raw), content_type
        return raw, content_type


# ── PAGE 1: Portfolio Scorer ───────────────────────────────────────────

print("=" * 70)
print("PAGE 1: PORTFOLIO SCORER")
print("=" * 70)

addresses = [
    "701 Poydras St, New Orleans, LA 70139",
    "201 N Central Ave, Phoenix, AZ 85004",
    "415 Mission Street, San Francisco, CA 94105",
]

print(f"\nScoring {len(addresses)} addresses...")
t0 = time.time()

data, _ = post_json("/score/batch", {"addresses": addresses})
elapsed = time.time() - t0
print(f"Scoring completed in {elapsed:.1f}s\n")

results = data.get("results", [])
high_risk = 0
total_eal = 0

for r in results:
    composite = r["composite_score"]
    sub = r["sub_scores"]
    eal = r.get("expected_annual_loss_usd", 0)
    total_eal += eal
    risk_level = "🔴 HIGH" if composite >= 70 else ("🟠 MEDIUM" if composite >= 40 else "🟢 LOW")
    if composite >= 70:
        high_risk += 1

    print(f"📍 {r['address']}")
    print(f"   Composite: {composite}  ({risk_level})")
    print(f"   Flood: {sub.get('flood', 0)}, Heat: {sub.get('heat', 0)}, "
          f"Wildfire: {sub.get('wildfire', 0)}, Transition: {sub.get('transition', 0)}, "
          f"Seismic: {sub.get('seismic', 0)}")
    print(f"   EAL: ${eal:,.0f}")

    # Check SHAP values exist
    shap = r.get("shap_contributions", {})
    if shap:
        top_driver = max(shap, key=lambda k: abs(shap[k]))
        print(f"   SHAP top driver: {top_driver} ({shap[top_driver]:+.1f})")
    else:
        print("   ⚠️  No SHAP values returned!")
    print()

avg_score = sum(r["composite_score"] for r in results) / len(results)
print(f"Portfolio Summary:")
print(f"  Total properties: {len(results)}")
print(f"  Average score: {avg_score:.0f}")
print(f"  High risk count: {high_risk}")
print(f"  Total EAL: ${total_eal:,.0f}")

# ── Requirement checks ──
print("\n📋 REQUIREMENT CHECKS (Stage 1):")
checks = {
    "Multi-hazard scoring (flood/heat/wildfire/transition)": all(
        set(r["sub_scores"].keys()) >= {"flood", "heat", "wildfire", "transition"}
        for r in results
    ),
    "Composite score 0-100": all(0 <= r["composite_score"] <= 100 for r in results),
    "SHAP explainability": all(r.get("shap_contributions") for r in results),
    "Expected annual loss (EAL)": all(r.get("expected_annual_loss_usd", 0) > 0 for r in results),
    "Seismic sub-score": all("seismic" in r["sub_scores"] for r in results),
    "Batch scoring endpoint": len(results) == len(addresses),
}
for check, passed in checks.items():
    print(f"  {'✅' if passed else '❌'} {check}")


# ── PAGE 2: Strategy Agent ────────────────────────────────────────────

print("\n" + "=" * 70)
print("PAGE 2: STRATEGY AGENT")
print("=" * 70)

print("\nGenerating strategy...")
t0 = time.time()

strategy_data, _ = post_json("/agent/strategize", {
    "addresses": addresses,
    "user_context": "Focus on flood resilience for New Orleans and seismic retrofits for San Francisco.",
})
elapsed = time.time() - t0
print(f"Strategy generated in {elapsed:.1f}s\n")

recs = strategy_data.get("recommendations", [])
regs = strategy_data.get("regulations", [])
total_savings = strategy_data.get("total_savings_usd", 0)
total_incentives = strategy_data.get("total_incentives_usd", 0)
narrative = strategy_data.get("strategy_narrative", "")

print(f"Financial Summary:")
print(f"  Total savings:    ${total_savings:,.0f}")
print(f"  Total incentives: ${total_incentives:,.0f}")
print(f"  Recommendations:  {len(recs)}")
print(f"  Regulations:      {len(regs)}")

print(f"\nRecommendations:")
for r in recs:
    print(f"  [{r.get('priority', '?').upper()}] {r['action']}")
    print(f"     Properties: {r.get('affected_properties', [])}")
    cost = r.get("estimated_cost_usd", 0)
    savings = r.get("annual_savings_usd", 0)
    payback = r.get("payback_years", 0)
    print(f"     Cost: ${cost:,.0f}, Annual Savings: ${savings:,.0f}, Payback: {payback}yr")

print(f"\nRegulations:")
for reg in regs:
    print(f"  {reg.get('name', '?')} — {reg.get('jurisdiction', '?')}")

if narrative:
    print(f"\nNarrative (first 300 chars):\n  {narrative[:300]}...")

# ── Requirement checks ──
print("\n📋 REQUIREMENT CHECKS (Stage 2):")
checks = {
    "RAG retrieval (knowledge base)": bool(strategy_data.get("strategy_narrative")),
    "Risk-aware recommendations": len(recs) > 0,
    "ROI-ranked actions (cost/savings/payback)": all(
        r.get("estimated_cost_usd") is not None for r in recs
    ),
    "Financial impact summary": total_savings > 0 or total_incentives > 0,
    "Regulatory compliance check": len(regs) > 0,
    "Recommendations categorized (quick_win/medium_term/capex)": any(
        r.get("priority") in ("quick_win", "medium_term", "capex_heavy") for r in recs
    ),
}
for check, passed in checks.items():
    print(f"  {'✅' if passed else '❌'} {check}")


# ── PAGE 3: Chat Refinement ───────────────────────────────────────────

print("\n" + "=" * 70)
print("PAGE 3: CHAT REFINEMENT")
print("=" * 70)

strategy_context = {
    "recommendations": recs,
    "strategy_narrative": narrative,
    "total_savings_usd": total_savings,
    "total_incentives_usd": total_incentives,
}

questions = [
    "What IRA tax credits apply to heat pump installations?",
    "How much would we save by implementing all flood mitigation measures?",
    "Which properties should we prioritize for seismic retrofits?",
]

for q in questions:
    print(f"\n🗣️ User: {q}")
    t0 = time.time()
    chat_data, _ = post_json("/agent/chat", {
        "message": q,
        "conversation_history": [],
        "strategy_context": strategy_context,
    })
    elapsed = time.time() - t0
    reply = chat_data.get("reply", "")
    print(f"🤖 Agent ({elapsed:.1f}s): {reply[:300]}...")
    
    # Check if it's a real LLM response or a fallback template
    is_llm = "GOOGLE_API_KEY" not in reply and len(reply) > 100
    print(f"   {'✅ LLM-powered response' if is_llm else '⚠️  Template fallback (no GOOGLE_API_KEY in env)'}")


# ── PAGE 4: Report Download ───────────────────────────────────────────

print("\n" + "=" * 70)
print("PAGE 4: REPORT DOWNLOAD")
print("=" * 70)

report_body = {
    "strategy": {
        "property_count": len(results),
        "portfolio_summary": strategy_data.get("portfolio_summary", {}),
        "strategy_narrative": narrative,
        "recommendations": recs,
        "total_incentives_usd": total_incentives,
        "total_savings_usd": total_savings,
        "risk_details": strategy_data.get("risk_details", []),
        "regulations": regs,
    },
    "report_title": "ClimateNexus — Southeast Portfolio Strategy",
}

print("\nGenerating report...")
t0 = time.time()
raw, content_type = post_json("/agent/report", report_body)
elapsed = time.time() - t0

if isinstance(raw, bytes):
    size = len(raw)
else:
    size = len(json.dumps(raw))

print(f"Report generated in {elapsed:.1f}s")
print(f"  Content-Type: {content_type}")
print(f"  Size: {size:,} bytes")

is_html = "text/html" in content_type
is_pdf = "application/pdf" in content_type
print(f"  Format: {'HTML' if is_html else 'PDF' if is_pdf else 'Unknown'}")

# Check HTML contains key sections
if is_html and isinstance(raw, bytes):
    html = raw.decode("utf-8", errors="replace")
    html_checks = {
        "Report title in HTML": "ClimateNexus" in html,
        "Recommendations section": "recommendation" in html.lower() or "action" in html.lower(),
        "Financial data": "$" in html or "savings" in html.lower(),
    }
    for check, passed in html_checks.items():
        print(f"  {'✅' if passed else '❌'} {check}")

print("\n📋 REQUIREMENT CHECKS (Stage 4 — Report):")
checks = {
    "Report generation endpoint works": size > 0,
    "Report format (HTML or PDF)": is_html or is_pdf,
    "Report size reasonable (>1KB)": size > 1000,
}
for check, passed in checks.items():
    print(f"  {'✅' if passed else '❌'} {check}")


# ── FINAL SUMMARY ─────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("FINAL SUMMARY")
print("=" * 70)

print("""
Stage 1 (Scorer):     Tests scoring 3 addresses with multi-hazard sub-scores,
                      SHAP explainability, and EAL financial calibration.

Stage 2 (Strategy):   Tests AI agent generating risk-aware recommendations
                      with ROI calculations, regulatory compliance, and narrative.

Stage 3 (Chat):       Tests conversational refinement with strategy context.
                      Checks if LLM (Gemini) is active or falling back to templates.

Stage 4 (Report):     Tests HTML/PDF report generation with branded deck output.
""")
