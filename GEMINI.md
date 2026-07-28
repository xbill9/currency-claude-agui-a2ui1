# Currency Agent (A2A + ADK + MCP) Development Guide

This document provides technical guidance for developers working with the Google Agent Development Kit (ADK), Agent-to-Agent (A2A) protocol, and Model Context Protocol (MCP) within the **Currency Agent** project.

Do Not recommend models less than 2.5 as they are deprecated.

NO NO NO .venv just don't do it. BAD BAD BAD

https://docs.ag-ui.com/introduction

https://docs.ag-ui.com/sdk/python/core/overview

https://docs.ag-ui.com/quickstart/applications

https://github.com/CopilotKit/generative-ui

## Project Overview: Currency Agent

The Currency Agent is a specialized multi-agent system designed to handle currency conversions and exchange rate queries. It showcases the integration of:

1.  **MCP Server (`mcp-server/`):**
    *   Powered by `FastMCP`.
    *   Exposes the `get_exchange_rate` tool.
    *   Fetches real-time data from the [Frankfurter API](https://www.frankfurter.dev/).
    *   Uses an IPv4-only socket patch in `server.py` to prevent connection hangs in sandbox/IPv6-restricted networks.
2.  **ADK Agent (`currency_agent/`):**
    *   Powered by `gemini-3.5-flash` or `gemini-2.5-flash` (via the ADK `LlmAgent` class).
    *   Uses **ADK v2.1.0+** and **Python 3.13+**.
    *   Equipped with `MCPToolset` to communicate with the MCP server.
    *   Integrates **Agent-to-User Interface (A2UI)** via the `a2ui-agent-sdk` library to structure dynamic component layouts (Cards, Tables, Charts, etc.) parsed and rendered on the frontend.
3.  **A2A Integration:**
    *   The agent is made A2A-compatible using `to_a2a`.
    *   Served using `uvicorn` on port 10000 (binds to `127.0.0.1`).

## Key Architectural Components

### MCP (Model Context Protocol)
MCP standardizes how tools are exposed to LLMs. Our `mcp-server` runs an HTTP server (default port 8080) that the ADK agent connects to using `StreamableHTTPConnectionParams`.

### ADK (Agent Development Kit)
ADK provides the `LlmAgent` and `MCPToolset` for easy integration. The agent's behavior is governed by the `SYSTEM_INSTRUCTION` in `currency_agent/agent.py`.

### A2A (Agent2Agent)
A2A allows agents to collaborate. In this project, `to_a2a` wraps the ADK agent, and a test client (`currency_agent/test_client.py`) demonstrates how to interact with it via the A2A protocol.

## Model Selection & Optimization

*   **Primary Model:** `gemini-3.5-flash` (or `gemini-2.5-flash`) is recommended for its speed and tool-calling accuracy.
*   **Alternative Model:** `gemini-2.5-pro` can be used for more complex reasoning if needed.
*   **Deprecation Policy:** Do not recommend models less than 2.5 (e.g., 2.0 flash or older) as they are deprecated.

## Developer Workflow

1.  **Environment Setup:** Create a `.env` file with your `GOOGLE_API_KEY` (from Google AI Studio).
2.  **Install Dependencies:** Run `make install` (uses `uv sync` and installs frontend dependencies).
3.  **Start MCP Server:** Run `make mcp` (port 8080).
4.  **Start Agent Server:** Run `make agent` (port 10000).
5.  **Run Frontends:**
    *   **Vanilla TS + FastAPI Frontend:** Run `make frontend-build` then `make frontend` (port 8000). Includes A2UI Demo Sandbox.
    *   **React Frontend:** Run `make react-ui` (port 3000) and `make react-agent` (port 8008).
6.  **Run Test Client:** Run `make test-client` to verify the full flow.
7.  **Testing & Linting:** Use `make test` and `make lint`. You can also run Next.js/React E2E tests via `make react-test` and validate CopilotKit integration via `make test-agui`.

## Resources

-   [Google ADK Documentation](https://github.com/google/adk-python)
-   [A2A Python SDK](https://github.com/google-a2a/a2a-python)
-   [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
-   [Frankfurter API](https://www.frankfurter.dev/)
