"""Recount archived runs.

usage:
  python3 tally.py bar  evidence/bar-values-vs-mcp.txt
  python3 tally.py demo evidence/macro-prompts-5x.jsonl
"""

import collections
import json
import sys

kind, path = sys.argv[1:3]
with open(path) as fh:
    lines = fh.readlines()
tally = collections.Counter()
totals = collections.Counter()

if kind == "bar":
    prompt = None
    for line in lines:
        if line.startswith("## "):
            prompt = line[3:].strip()
        elif line.strip().startswith("identical :"):
            same = line.split(":", 1)[1].strip() == "True"
            outcome = "bar chart, values identical" if same else "no bar chart"
            tally[(prompt, outcome)] += 1
            totals[prompt] += 1
else:
    for line in lines:
        d = json.loads(line)
        comps = {c for u in d.get("ui", []) for c in u["components"]}
        if comps:
            outcome = "rendered A2UI"
        elif "<a2ui>" in d.get("text", ""):
            outcome = "Express block as plain text, no UI"
        else:
            outcome = "other"
        if "get_exchange_rate" in d.get("tools", []):
            outcome += ", called the MCP rate tool"
        tally[(d["prompt"], outcome)] += 1
        totals[d["prompt"]] += 1

for (prompt, outcome), n in sorted(tally.items()):
    print(f"{n} of {totals[prompt]}: {outcome} | {prompt}")
