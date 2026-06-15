import urllib.request
import json

BASE = "http://localhost:8000"

def gql(query, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE}/api/v1/graphql",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        r = urllib.request.urlopen(req, timeout=8)
        result = json.loads(r.read().decode())
        return result
    except urllib.error.HTTPError as e:
        return {"httpError": e.code, "body": e.read().decode()}
    except Exception as e:
        return {"exception": str(e)}

# 1. Health check
print("=== /health ===")
try:
    r = urllib.request.urlopen(f"{BASE}/health", timeout=5)
    print(r.status, r.read().decode()[:200])
except Exception as e:
    print("ERROR:", e)

# 2. createDmRoom mutation
print("\n=== createDmRoom ===")
Q = """
mutation CreateDmRoom($createdBy: String!, $userA: String!, $userB: String!) {
  createDmRoom(createdBy: $createdBy, userA: $userA, userB: $userB) {
    roomId
    name
  }
}
"""
result = gql(Q, {"createdBy": "alice", "userA": "alice", "userB": "bob"})
print(json.dumps(result, indent=2))
