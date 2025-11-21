$py = @'
import os, json, requests
MCP = os.getenv("TAVILY_MCP_URL", "https://mcp.tavily.com/mcp/?tavilyApiKey=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")
print("Testing MCP URL:", MCP)
headers = {"User-Agent":"personal-ai-local/1.0", "Content-Type":"application/json"}

payload = {"query":"weather in Singapore", "top_k": 3}
print("\n=== POST JSON ===")
try:
    r = requests.post(MCP, headers=headers, json=payload, timeout=20)
    print("POST status:", r.status_code)
    print("POST headers:", dict(r.headers))
    txt = r.text[:2000]
    print("POST body (first 2000 chars):\\n", txt)
    try:
        j = r.json()
        print("POST parsed keys:", list(j.keys())[:10])
        results = j.get("results") or j.get("data") or j.get("hits") or j.get("items") or j.get("documents") or []
        print("POST results count:", len(results))
        if results:
            print("First result keys:", list(results[0].keys())[:20])
            print("First result snippet (first 800 chars):")
            print(json.dumps(results[0], indent=2)[:800])
    except Exception as e:
        print("POST json parse error:", e)
except Exception as e:
    print("POST request exception:", e)

print("\n=== GET fallback (query params) ===")
try:
    params = {"query":"weather in Singapore", "top_k": 3}
    r2 = requests.get(MCP, headers=headers, params=params, timeout=20)
    print("GET status:", r2.status_code)
    print("GET url (with params):", r2.url)
    txt2 = r2.text[:2000]
    print("GET body (first 2000 chars):\\n", txt2)
    try:
        j2 = r2.json()
        print("GET parsed keys:", list(j2.keys())[:10])
        results2 = j2.get("results") or j2.get("data") or j2.get("hits") or j2.get("items") or j2.get("documents") or []
        print("GET results count:", len(results2))
        if results2:
            print("First result keys:", list(results2[0].keys())[:20])
            print("First result snippet (first 800 chars):")
            print(json.dumps(results2[0], indent=2)[:800])
    except Exception as e:
        print("GET json parse error:", e)
except Exception as e:
    print("GET request exception:", e)
'@