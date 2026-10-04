from __future__ import annotations

import json
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2) as response:
    payload = json.load(response)
    assert response.status == 200
    assert payload["status"] == "ok"

print("Health smoke test passed.")
