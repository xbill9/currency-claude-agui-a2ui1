"""Send candidate demo prompts through Next.js and summarise what renders."""

import json
import sys
import time
import uuid

import httpx

URL = "http://localhost:3000/api/copilotkit/agent/currency_agent/run"

PROMPTS = [
    "How much is 250 USD in EUR?",
    "Show me the USD to JPY trend over the last 90 days",
    "Compare 1 USD in EUR, GBP, JPY and CAD",
    "I'm going to Japan with 2000 Canadian dollars. How many yen is that?",
    "How has the British pound done against the euro this year?",
    "Convert 100 USD to XYZ",
    "What's the weather in Paris?",
]


def run(prompt: str) -> dict:
    rid = uuid.uuid4().hex[:8]
    body = {
        "runId": f"demo-{rid}",
        "threadId": f"demo-thread-{rid}",
        "tools": [],
        "context": [],
        "state": {},
        "messages": [{"id": f"m-{rid}", "role": "user", "content": prompt}],
    }
    tools, text, ui, errors = [], "", [], []
    t0 = time.time()
    with httpx.Client(timeout=120) as c, c.stream("POST", URL, json=body) as r:
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            ev = json.loads(line[5:])
            t = ev.get("type")
            if t == "TOOL_CALL_START":
                tools.append(ev.get("toolCallName"))
            elif t == "TEXT_MESSAGE_CONTENT":
                text += ev.get("delta", "")
            elif t == "RUN_ERROR":
                errors.append(ev.get("message"))
            elif t == "TOOL_CALL_RESULT":
                content = ev.get("content")
                try:
                    content = (
                        json.loads(content) if isinstance(content, str) else content
                    )
                except json.JSONDecodeError:
                    errors.append(f"unparsable tool result: {str(content)[:120]}")
                    continue
                if isinstance(content, dict):
                    for m in content.get("validated_a2ui_json") or []:
                        comps = (m.get("createSurface") or {}).get("components") or []
                        ui.append(
                            {
                                "components": [x.get("component") for x in comps],
                                "texts": [
                                    x.get("text")
                                    for x in comps
                                    if x.get("component") == "Text"
                                ],
                                "charts": [
                                    {
                                        "type": x.get("component"),
                                        "title": x.get("title"),
                                        "points": len(x.get("values") or []),
                                        "labels": (x.get("labels") or [])[:6],
                                    }
                                    for x in comps
                                    if x.get("component") in ("LineChart", "BarChart")
                                ],
                            }
                        )
                    if not content.get("validated_a2ui_json"):
                        errors.append(f"tool result: {json.dumps(content)[:200]}")
    return {
        "prompt": prompt,
        "seconds": round(time.time() - t0, 1),
        "tools": tools,
        "ui": ui,
        "text": text.strip()[:300],
        "errors": errors,
    }


if __name__ == "__main__":
    prompts = sys.argv[1:] or PROMPTS
    for p in prompts:
        try:
            print(json.dumps(run(p), ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"prompt": p, "errors": [repr(e)]}))
