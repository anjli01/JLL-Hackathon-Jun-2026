import json, urllib.request

req = urllib.request.Request('http://127.0.0.1:8001/agent/strategize', method='POST')
req.add_header('Content-Type', 'application/json')
data = json.dumps({
    "addresses": [
      "415 Mission Street, San Francisco, CA 94105",
      "1100 Louisiana Street, Houston, TX 77002"
    ],
    "user_context": "Focus on seismic resilience for SF and flood mitigation for Houston."
})
with urllib.request.urlopen(req, data=data.encode('utf-8')) as response:
    d = json.loads(response.read().decode('utf-8'))

    print(f"Total Savings: ${d.get('total_savings_usd')}")
    print(f"Total Incentives: ${d.get('total_incentives_usd')}")
    print("\nRecommendations:")
    for r in d.get('recommendations', []):
        print(f"  [{r['priority'].upper()}] {r['action']}")
        print(f"    Targeted Properties: {r.get('affected_properties')}")
    print("\nRegulations:")
    for reg in d.get('regulations', []):
        print(f"  {reg['name']} - {reg['jurisdiction']}")
    
    with open('data/strategy.json', 'w') as f:
        json.dump(d, f)
