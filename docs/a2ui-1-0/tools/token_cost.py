"""How many tokens the model writes for the same UI on A2UI 0.9 and on 1.0.

For three answers the agent gives (a rate card, a 90-day history chart and a
three-currency comparison) this builds the UI once, with live rates, and then
writes it four ways:

  0.9 JSON        what the 0.9 build's model wrote: three messages, figures typed in
  1.0 JSON        the same components as one 1.0 createSurface
  1.0 Express     the same components as an Express block (decompiled from the JSON)
  1.0 macro       the Express block the model writes with server-side macros

Each text is counted with the Gemini countTokens API, so the counts are the
model's own tokenizer. JSON is compact (no indentation). Properties left at
their default (Text variant "body", Divider axis "horizontal", Column justify
"start" and align "stretch") are removed from every form, and a 1.0 surface whose
components share one catalog names it once on createSurface.

usage: python3 docs/a2ui-1-0/tools/token_cost.py [model]
"""

import copy
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from a2ui.core.schema.v1_0 import AgentToRendererMessage
from a2ui.inference_formats.express import (
    ExpressCompiler,
    ExpressDecompiler,
)
from pydantic import TypeAdapter

from currency_agent.agent import (
    BASE_CATALOGS,
    INFERENCE_CATALOGS,
    macro_expander,
)

MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemini-2.5-flash"
with open(os.path.expanduser("~/gemini.key")) as fh:
    KEY = fh.read().strip()

CASES = [
    ("Rate card", 'surface("main")\nroot = RateCard("USD", "EUR", 100)\n'),
    ("90-day chart", 'surface("main")\nroot = RateHistoryChart("USD", "JPY", 90)\n'),
    (
        "3-currency comparison",
        'surface("main")\nroot = RateComparison("USD", ["EUR", "GBP", "CHF"])\n',
    ),
]

adapter = TypeAdapter(AgentToRendererMessage)


def count(text):
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:countTokens",
        data=json.dumps({"contents": [{"parts": [{"text": text}]}]}).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": KEY},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["totalTokens"]


def expand(src):
    msgs = ExpressCompiler(INFERENCE_CATALOGS).compile(src, surface_id="main")
    typed = [
        adapter.validate_python(m.model_dump(by_alias=True, exclude_none=True))
        for m in msgs
    ]
    return [
        m.model_dump(by_alias=True, exclude_none=True)
        for m in macro_expander.transform_to_transport(typed)
    ]


DEFAULTS = {
    "variant": "body",
    "axis": "horizontal",
    "justify": "start",
    "align": "stretch",
}


def tidy(wire):
    """Drop default-valued props; hoist a single shared catalogId."""
    wire = copy.deepcopy(wire)
    for m in wire:
        cs = m["createSurface"]
        for c in cs["components"]:
            for k, v in DEFAULTS.items():
                if c.get(k) == v:
                    del c[k]
        cats = {c.get("catalogId") for c in cs["components"]}
        if len(cats) == 1:
            for c in cs["components"]:
                c.pop("catalogId", None)
            cs["catalogId"] = cats.pop()
            cs["components"] = cs.pop("components")
    return wire


def to_0_9(wire):
    """The same components in the 0.9 shape: an empty createSurface, then
    updateComponents; plain keys; headings as an h3 variant, since 0.9 Text
    has heading variants and 1.0 takes Markdown."""
    out = []
    for m in wire:
        cs = m["createSurface"]
        comps = []
        for c in copy.deepcopy(cs["components"]):
            c.pop("catalogId", None)
            t = c.get("text")
            if c["component"] == "Text" and isinstance(t, str) and t.startswith("### "):
                c["text"], c["variant"] = t[4:], "h3"
            comps.append(c)
        out.append(
            {
                "version": "v0.9",
                "createSurface": {
                    "surfaceId": cs["surfaceId"],
                    "catalogId": "https://a2ui.org/catalog/currency-charts",
                },
            }
        )
        out.append(
            {
                "version": "v0.9",
                "updateComponents": {"surfaceId": cs["surfaceId"], "components": comps},
            }
        )
    return out


def compact(v):
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False)


decompiler = ExpressDecompiler(BASE_CATALOGS, version="1.0")
print(f"# Tokens the model writes for the same UI, counted by {MODEL} countTokens")
print("| Answer | Components | 0.9 JSON | 1.0 JSON | 1.0 Express | 1.0 macro |")
print("| :--- | ---: | ---: | ---: | ---: | ---: |")
dumps = []
for name, src in CASES:
    wire = tidy(expand(src))
    express = decompiler.decompile([adapter.validate_python(m) for m in wire])
    if not isinstance(express, str):
        express = "\n".join(map(str, express))
    v09 = to_0_9(wire)
    n = len(wire[0]["createSurface"]["components"])
    texts = [compact(v09), compact(wire), express, src]
    toks = [count(t) for t in texts]
    print(f"| {name} | {n} | {toks[0]} | {toks[1]} | {toks[2]} | {toks[3]} |")
    dumps.append((name, texts))

for name, texts in dumps:
    print(f"\n## {name}")
    for label, t in zip(["0.9 JSON", "1.0 JSON", "1.0 Express", "1.0 macro"], texts):
        print(f"### {label} ({len(t)} chars)\n{t}")
