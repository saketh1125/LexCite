import json
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/opencode/eval_results.json"
CASES = json.load(open("eval/test_cases.json", encoding="utf-8"))

# rate limiter on the server throttles to 40/min; stay under it at ~20/min
DELAY = 3.0
results = []
for case in CASES:
    q = case["question"]
    for attempt in range(3):
        try:
            r = httpx.post(f"{BASE}/ask", json={"question": q}, timeout=120)
            r.raise_for_status()
            break
        except Exception as exc:
            print(f"retry {attempt} for #{case['id']}: {exc}", flush=True)
            time.sleep(5)
    else:
        print(f"FAILED #{case['id']} after retries", flush=True)
        continue
    data = r.json()
    results.append(
        {
            "id": case["id"],
            "question": q,
            "answer": data["answer"],
            "citations": data["citations"],
            "trace": data["trace"],
        }
    )
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"#{case['id']} done: {len(data['citations'])} citations", flush=True)
    time.sleep(DELAY)
