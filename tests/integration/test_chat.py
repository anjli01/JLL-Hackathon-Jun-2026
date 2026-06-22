import json, urllib.request

strategy = json.load(open('data/strategy.json'))
strategy_context = {
    "recommendations": strategy.get("recommendations", []),
    "strategy_narrative": strategy.get("strategy_narrative", ""),
    "total_savings_usd": strategy.get("total_savings_usd", 0),
    "total_incentives_usd": strategy.get("total_incentives_usd", 0),
}

req = urllib.request.Request('http://127.0.0.1:8001/agent/chat', method='POST')
req.add_header('Content-Type', 'application/json')
data = json.dumps({
    "message": "How much would we save by implementing all flood mitigation measures?",
    "conversation_history": [],
    "strategy_context": strategy_context
})

with urllib.request.urlopen(req, data=data.encode('utf-8')) as response:
    d = json.loads(response.read().decode('utf-8'))
    print(f"Chat Reply:\n{d.get('reply')}")
