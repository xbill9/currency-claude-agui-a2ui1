"""Show what the model wrote and what reached the browser, for each prompt.

usage: python3 capture.py "prompt" ["prompt" ...]
"""

import collections
import json
import sys
import uuid

import httpx

URL = "http://localhost:3000/api/copilotkit/agent/currency_agent/run"

for prompt in sys.argv[1:]:
    rid = uuid.uuid4().hex[:8]
    body = {
        "runId": rid,
        "threadId": f"t{rid}",
        "tools": [],
        "context": [],
        "state": {},
        "messages": [{"id": f"m{rid}", "role": "user", "content": prompt}],
    }
    calls, results, text = [], [], ""
    with httpx.Client(timeout=120) as c, c.stream("POST", URL, json=body) as r:
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            ev = json.loads(line[5:])
            if ev["type"] == "TOOL_CALL_START":
                calls.append(ev["toolCallName"])
            elif ev["type"] == "TOOL_CALL_ARGS":
                calls[-1] += " " + ev["delta"]
            elif ev["type"] == "TEXT_MESSAGE_CONTENT":
                text += ev["delta"]
            elif ev["type"] == "TOOL_CALL_RESULT":
                content = json.loads(ev["content"])
                results.extend(content.get("validated_a2ui_json") or [])
    print(f"## {prompt}")
    print("### What the model wrote")
    for call in calls:
        name, _, args = call.partition(" ")
        payload = json.loads(args).get("a2ui_payload", args) if args else ""
        print(f"{name}:\n{payload}")
    if text.strip():
        print(f"reply text: {text.strip()}")
    print("### What reached the browser")
    for m in results:
        surface = m.get("createSurface") or {}
        comps = surface.get("components") or []
        print(
            f"version {m['version']}, {[k for k in m if k != 'version']}, {len(comps)} components"
        )
        by = collections.defaultdict(list)
        for x in comps:
            by[x.get("catalogId")].append(x["component"])
        for cat, names in by.items():
            print(f"  {cat}: {names}")
        for x in comps:
            if x["component"] == "Text":
                print(f"  Text: {x['text']}")
            if x["component"] in ("BarChart", "LineChart"):
                vals = x["values"]
                shown = vals if len(vals) <= 10 else f"{len(vals)} points"
                print(
                    f"  {x['component']}: {x.get('title')} | {x['labels'][:10]} | {shown}"
                )
    print()
