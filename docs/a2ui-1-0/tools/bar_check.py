"""Compare BarChart values with the get_exchange_rate results in the same run.

usage: python3 bar_check.py RUNS "prompt" ["prompt" ...]
"""

import collections
import json
import sys
import uuid

import httpx

URL = "http://localhost:3000/api/copilotkit/agent/currency_agent/run"

runs = int(sys.argv[1])
tally = collections.Counter()
for prompt in [p for p in sys.argv[2:] for _ in range(runs)]:
    rid = uuid.uuid4().hex[:8]
    body = {
        "runId": rid,
        "threadId": f"t{rid}",
        "tools": [],
        "context": [],
        "state": {},
        "messages": [{"id": f"m{rid}", "role": "user", "content": prompt}],
    }
    mcp, bars, problems = {}, None, []
    with httpx.Client(timeout=120) as c, c.stream("POST", URL, json=body) as r:
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            ev = json.loads(line[5:])
            if ev.get("type") != "TOOL_CALL_RESULT":
                continue
            co = ev["content"]
            co = json.loads(co) if isinstance(co, str) else co
            if isinstance(co, dict) and "error" in co:
                problems.append(str(co["error"])[:200])
                continue
            if "structuredContent" in co:
                s = co["structuredContent"]
                for k, v in s["rates"].items():
                    mcp[f"{s['base']}->{k}"] = v
            for m in co.get("validated_a2ui_json") or []:
                for x in (m.get("createSurface") or {}).get("components") or []:
                    if x.get("component") == "BarChart":
                        bars = dict(zip(x["labels"], x["values"]))
    mcp_values = sorted(mcp.values())
    bar_values = sorted((bars or {}).values())
    print(f"## {prompt}")
    print(f"   MCP rates : {mcp}")
    print(f"   bar values: {bars}")
    same = bars is not None and mcp_values == bar_values
    print(f"   identical : {same}")
    if problems:
        print(f"   tool errors: {problems}")
    outcome = (
        "bar chart, values identical"
        if same
        else ("bar chart, values differ" if bars else "no bar chart")
    )
    tally[(prompt, outcome)] += 1

print("\n# Tally")
for (prompt, outcome), n in sorted(tally.items()):
    print(f"{n} of {runs}: {outcome} | {prompt}")
