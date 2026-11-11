# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Currency agent: Google ADK `LlmAgent` (Gemini) + FastMCP tool server + A2UI 1.0 generative UI, served to a Next.js/CopilotKit front end over AG-UI. The repo name says "claude" but the agent runs on Gemini.

## Running Python: python3 only, never `uv run`

The Makefile, `frontend-react/scripts/run-agent.sh`, `setup-agent.sh` and npm `postinstall` all call `uv run`/`uv sync`. That creates a `.venv/` and silently re-resolves `uv.lock` (e.g. bumps a2a-sdk 0.3.3 → 0.3.26). Do not use them. The active pyenv `python3` already has every dependency; run things with it directly:

| What | Command (from repo root unless noted) |
|---|---|
| MCP server, :8080 `/mcp` | `python3 mcp-server/server.py` |
| A2A agent server, :10000 (`/health`) | `python3 -m uvicorn currency_agent.agent:a2a_app --host 127.0.0.1 --port 10000` |
| AG-UI bridge, :8008 (`/health`) | `cd frontend-react/agent && python3 main.py` |
| Next.js UI, :3000 | `cd frontend-react && npm run dev:ui` (never `npm run dev` / `dev:agent`; `npm install --ignore-scripts`) |
| Legacy UI, :8000 | `PORT=8000 AGENT_SERVER_URL=http://127.0.0.1:10000 python3 frontend/main.py` (needs `frontend/frontend` built) |
| Lint / format | `ruff check . && ruff format --check .` / `ruff format . && ruff check --fix .` |
| Tests | `python3 -m pytest mcp-server/test_server.py` (needs :8080 up); `PYTHONPATH=frontend python3 -m pytest frontend/tests` |
| AG-UI end-to-end | `python3 frontend-react/scripts/validate_agui.py [--target nextjs\|direct]`; `python3 frontend-react/scripts/test_react_e2e.py` (needs :3000 + :8008) |

The lint baseline already fails (77 `ruff check` errors and 2 unformatted files on 2026-11-11), so judge lint on the lines you changed. A PostToolUse hook in `.claude/settings.json` runs `ruff format` + `ruff check --fix` on every `.py` file Claude edits, which can also fix pre-existing issues elsewhere in that file. Check `git diff` before committing.

`make stop` and `make status` are safe (no uv). Run services in the background with logs to `mcp.log`, `agent.log`, `react-agent.log`, `react-ui.log` (gitignored) to match the Makefile. If `uv.lock` or `.venv/` shows up in `git status`, revert/remove it. Use `/verify-stack` to check a change end to end.

## Architecture

- **Main path is AG-UI + React:** browser → Next `/api/copilotkit` (`AGENT_URL`, default `http://localhost:8008/`) → `frontend-react/agent/main.py`, which imports `currency_agent.agent.root_agent` in-process → MCP on :8080. The A2A server (:10000) is a second entry point to the same agent and is what `cloudbuild.yaml` deploys to Cloud Run; keep it working.
- **Legacy `frontend/`** (FastAPI + Vite, talks A2A on :10000) was not migrated to A2UI 1.0 but must keep working — update it alongside changes that affect it. Its `Makefile`/`package.json` names are leftovers from another project.
- **Model:** target `gemini-3.8-flash`, set via `GENAI_MODEL` (code default in `currency_agent/agent.py` is still `gemini-2.5-flash`). Never suggest models older than 2.5.

## A2UI 1.0 pipeline (`currency_agent/agent.py`, `macros.py`)

- The model writes A2UI **Express** format (`A2uiRequestProcessor` default). `MacroSendA2uiToClientToolset._parse_payload` compiles it, validates against `INFERENCE_CATALOGS` (base + macro sidecar), runs `macro_expander.transform_to_transport`, then re-validates against `BASE_CATALOGS` (Basic 1.0 + charts). Both validations must pass.
- **Server-side macros** (`RateCard`, `RateHistoryChart`) fetch rates from Frankfurter on the server so figures never pass through the model. Treat macro arguments as untrusted: validate (`_code`) and clamp. Adding one: `/add-a2ui-macro`.
- The charts catalog id `https://a2ui.org/catalog/currency-charts/v1/catalog.json` and component props must match between `currency_agent/custom_catalog.json` and `frontend-react/src/components/A2UICustomCatalog.tsx`.
- CopilotKit's built-in A2UI middleware speaks v0.9, so it is disabled in `route.ts`; rendering goes through `useRenderTool("send_a2ui_json_to_client")` reading `validated_a2ui_json`. Re-sending `createSurface` for a live surface fails. `@a2ui/react` must load client-only.

## Gotchas

- `currency_agent/__init__.py` monkeypatches run before imports (hence ruff `E402` ignored): IPv4-only `getaddrinfo` (also in `server.py`, `agent.py`, `agent/main.py` — sandboxes hang on IPv6), OTel gen_ai attribute shims, MCP sampling shims, and ADK `_is_valid_state_name` disabled so `{...}` in prompts isn't treated as state. Don't remove them.
- `next.config.ts` has `ignoreBuildErrors: true` for a known CopilotKit `HttpAgent` type mismatch — `next build` passing doesn't mean types check.
- `frontend-react/agent` pins `a2a-sdk==0.3.3`; root allows `>=0.3.3`.
- Env: `GOOGLE_API_KEY`/`GEMINI_API_KEY` (or `GOOGLE_GENAI_USE_VERTEXAI` + `GOOGLE_CLOUD_PROJECT`/`LOCATION`), `GENAI_MODEL`, `MCP_SERVER_URL`. `set_env.sh` writes `.env` from `~/gemini.key`.

## Git

Commit straight to `master` and push. No branches or PRs.
