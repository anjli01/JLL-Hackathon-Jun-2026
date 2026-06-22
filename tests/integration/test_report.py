import json, urllib.request

strategy = json.load(open('data/strategy.json'))
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

req = urllib.request.Request('http://127.0.0.1:8001/agent/report', method='POST')
req.add_header('Content-Type', 'application/json')
data = json.dumps({
    "strategy": strategy_data,
    "report_title": "Texas & California Portfolio Strategy"
})

try:
    with urllib.request.urlopen(req, data=data.encode('utf-8')) as response:
        content_type = response.info().get_content_type()
        print(f"Report Generated! Content-Type: {content_type}")
        print(f"Response size: {len(response.read())} bytes")
except Exception as e:
    print(f"Error: {e}")
