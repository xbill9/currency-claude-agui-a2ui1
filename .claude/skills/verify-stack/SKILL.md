---
name: verify-stack
description: Start the currency agent stack (MCP, A2A agent, AG-UI bridge, Next.js UI) with python3, check health, run lint and the AG-UI end-to-end checks, then stop everything. Use after changing the agent, macros, catalog, MCP server or React UI to confirm the change works end to end.
---

Verify the stack end to end. Never use `uv run`, `uv sync`, the uv-based `make` targets, `npm run dev` or `npm run dev:agent` — they create `.venv/` and rewrite `uv.lock`. Run everything with the active `python3`.

1. **Lint:** `ruff check . && ruff format --check .` from the repo root. Report failures; don't auto-fix unless asked.

2. **Clean start:** `make stop` (safe, no uv). Check `.env` exists or `GOOGLE_API_KEY`/`GEMINI_API_KEY` is set; if neither, stop and tell the user.

3. **Start services in the background** (Bash `run_in_background`, or `nohup ... &`), logs at the repo root:
   - `nohup python3 mcp-server/server.py > mcp.log 2>&1 &`
   - `nohup python3 -m uvicorn currency_agent.agent:a2a_app --host 127.0.0.1 --port 10000 > agent.log 2>&1 &`
   - `(cd frontend-react/agent && nohup python3 main.py > ../../react-agent.log 2>&1 &)`
   - `(cd frontend-react && nohup npm run dev:ui > ../react-ui.log 2>&1 &)`

4. **Wait for health** with a bounded poll (Monitor with an until-loop, ~90 s max), not fixed sleeps:
   - `curl -sf http://127.0.0.1:10000/health`
   - `curl -sf http://127.0.0.1:8008/health`
   - port 8080 open (MCP), `curl -sf http://localhost:3000/api/copilotkit` (Next compiles on first hit)
   If one never comes up, show the tail of its log and go to step 7.

5. **Tests:**
   - `python3 -m pytest mcp-server/test_server.py`
   - `python3 frontend-react/scripts/validate_agui.py --target nextjs`
   - `python3 frontend-react/scripts/test_react_e2e.py`
   - If the change touched `frontend/`: `PYTHONPATH=frontend python3 -m pytest frontend/tests`
   - If the change touched the A2A path: `python3 frontend-react/scripts/validate_agui.py --target direct`

6. Scan `agent.log` and `react-agent.log` for tracebacks, A2UI validation errors, or `MacroExpander` errors even if tests passed.

7. **Always stop:** `make stop`. Then `git status --short`: if `uv.lock` changed or `.venv/` appeared, revert/remove it and say so.

Report each step as pass/fail with the exact failing output quoted. Don't claim a pass for a step that didn't run.
