"""Currency Agent Main Endpoint for AG-UI."""

from __future__ import annotations

import socket

# Force IPv4-only to avoid connection hangs on IPv6 in sandbox environments
if not hasattr(socket, "_original_getaddrinfo"):
    socket._original_getaddrinfo = socket.getaddrinfo

    def _ipv4_only_getaddrinfo(*args, **kwargs):
        return [
            r
            for r in socket._original_getaddrinfo(*args, **kwargs)
            if r[0] == socket.AF_INET
        ]

    socket.getaddrinfo = _ipv4_only_getaddrinfo

import os
import sys
from dotenv import load_dotenv
from fastapi import FastAPI
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint

load_dotenv()

# Add project root to sys.path to allow importing from currency_agent
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from currency_agent.agent import root_agent

# Create ADK middleware agent instance for currency agent
adk_currency_agent = ADKAgent(
    adk_agent=root_agent,
    user_id="demo_user",
    session_timeout_seconds=3600,
    use_in_memory_services=True,
)

# Create FastAPI app
app = FastAPI(title="ADK Middleware Currency Agent")

# Add the ADK endpoint
add_adk_fastapi_endpoint(app, adk_currency_agent, path="/")


@app.get("/capabilities")
async def capabilities():
    return {"capabilities": ["streaming"]}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  Warning: GOOGLE_API_KEY environment variable not set!")
        print("   Set it with: export GOOGLE_API_KEY='your-key-here'")
        print()

    port = int(os.getenv("PORT", 8008))
    uvicorn.run(app, host="0.0.0.0", port=port)
