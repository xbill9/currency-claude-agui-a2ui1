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

# Monkeypatch to fix ImportError: cannot import name 'GEN_AI_INPUT_MESSAGES' from 'opentelemetry'
try:
    import opentelemetry.semconv._incubating.attributes.gen_ai_attributes as gen_ai_attr

    if not hasattr(gen_ai_attr, "GEN_AI_INPUT_MESSAGES"):
        setattr(gen_ai_attr, "GEN_AI_INPUT_MESSAGES", "gen_ai.input.messages")
    if not hasattr(gen_ai_attr, "GEN_AI_OUTPUT_MESSAGES"):
        setattr(gen_ai_attr, "GEN_AI_OUTPUT_MESSAGES", "gen_ai.output.messages")
    if not hasattr(gen_ai_attr, "GEN_AI_RESPONSE_FINISH_REASONS"):
        setattr(
            gen_ai_attr,
            "GEN_AI_RESPONSE_FINISH_REASONS",
            "gen_ai.response.finish_reasons",
        )
    if not hasattr(gen_ai_attr, "GEN_AI_SYSTEM_INSTRUCTIONS"):
        setattr(gen_ai_attr, "GEN_AI_SYSTEM_INSTRUCTIONS", "gen_ai.system.instructions")
    if not hasattr(gen_ai_attr, "GEN_AI_USAGE_INPUT_TOKENS"):
        setattr(gen_ai_attr, "GEN_AI_USAGE_INPUT_TOKENS", "gen_ai.usage.input_tokens")
    if not hasattr(gen_ai_attr, "GEN_AI_USAGE_OUTPUT_TOKENS"):
        setattr(gen_ai_attr, "GEN_AI_USAGE_OUTPUT_TOKENS", "gen_ai.usage.output_tokens")
except ImportError:
    pass

# Monkeypatch to fix ImportError: cannot import name 'SamplingCapability' from 'mcp'
try:
    import mcp
    import mcp.types

    if not hasattr(mcp, "SamplingCapability"):
        setattr(mcp, "SamplingCapability", mcp.types.SamplingCapability)
except ImportError:
    pass

import os

os.environ["NO_GCE_CHECK"] = "true"

import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from a2a_utils import a2a_card_dispatch
from authenticated_httpx import create_authenticated_client
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from httpx_sse import aconnect_sse
from logging_config import get_uvicorn_log_config, setup_logging
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.trace import TracerProvider, export
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    MessageSendParams,
    SendStreamingMessageRequest,
    Message as A2AMessage,
    Part as A2APart,
    TextPart as A2ATextPart,
    Role as A2ARole,
)


class Feedback(BaseModel):
    score: float
    text: str | None = None
    run_id: str | None = None
    user_id: str | None = None


# Standardized logging setup
setup_logging("course-creator-web")
logger = logging.getLogger(__name__)

provider = TracerProvider()
if os.getenv("K_SERVICE") or os.getenv("ENABLE_TRACING"):
    try:
        processor = export.BatchSpanProcessor(
            CloudTraceSpanExporter(),
        )
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        logger.info("OpenTelemetry CloudTraceSpanExporter initialized.")
    except Exception as e:
        logger.warning(f"Could not initialize CloudTraceSpanExporter: {e}")
else:
    logger.info("OpenTelemetry Cloud Trace is disabled for local development.")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BaseHTTPMiddleware, dispatch=a2a_card_dispatch)

agent_name = os.getenv("AGENT_NAME", None)
agent_server_url = os.getenv("AGENT_SERVER_URL")
if agent_server_url:
    agent_server_url = agent_server_url.rstrip("/")

clients: dict[str, httpx.AsyncClient] = {}
a2a_clients: dict[str, A2AClient] = {}


async def get_client(agent_server_origin: str) -> httpx.AsyncClient:
    global clients
    if agent_server_origin not in clients:
        clients[agent_server_origin] = create_authenticated_client(agent_server_origin)
    return clients[agent_server_origin]


async def get_a2a_client(agent_server_origin: str) -> A2AClient:
    global a2a_clients
    if agent_server_origin not in a2a_clients:
        httpx_client = await get_client(agent_server_origin)
        resolver = A2ACardResolver(
            httpx_client=httpx_client,
            base_url=agent_server_origin,
        )
        agent_card = await resolver.get_agent_card()
        a2a_clients[agent_server_origin] = A2AClient(
            httpx_client=httpx_client,
            agent_card=agent_card,
        )
    return a2a_clients[agent_server_origin]


async def create_session(
    agent_server_origin: str, agent_name: str, user_id: str
) -> dict[str, Any]:
    httpx_client = await get_client(agent_server_origin)
    headers = [("Content-Type", "application/json")]
    session_request_url = (
        f"{agent_server_origin}/apps/{agent_name}/users/{user_id}/sessions"
    )
    session_response = await httpx_client.post(session_request_url, headers=headers)
    session_response.raise_for_status()
    return session_response.json()


async def get_session(
    agent_server_origin: str, agent_name: str, user_id: str, session_id: str
) -> dict[str, Any] | None:
    httpx_client = await get_client(agent_server_origin)
    headers = [("Content-Type", "application/json")]
    session_request_url = (
        f"{agent_server_origin}/apps/{agent_name}/users/{user_id}/sessions/{session_id}"
    )
    session_response = await httpx_client.get(session_request_url, headers=headers)
    if session_response.status_code == 404:
        return None
    session_response.raise_for_status()
    return session_response.json()


async def list_agents(agent_server_origin: str) -> list[str]:
    httpx_client = await get_client(agent_server_origin)
    headers = [("Content-Type", "application/json")]
    list_url = f"{agent_server_origin}/list-apps"
    list_response = await httpx_client.get(list_url, headers=headers)
    list_response.raise_for_status()
    agent_list = list_response.json()
    if not agent_list:
        agent_list = ["agent"]
    return agent_list


async def query_adk_server(
    agent_server_origin: str,
    agent_name: str,
    user_id: str,
    message: str,
    session_id: str,
) -> AsyncGenerator[dict[str, Any]]:
    httpx_client = await get_client(agent_server_origin)
    request = {
        "appName": agent_name,
        "userId": user_id,
        "sessionId": session_id,
        "newMessage": {"role": "user", "parts": [{"text": message}]},
        "streaming": True,
    }
    logger.info(
        f"Connecting to ADK server: {agent_server_origin}/run_sse with streaming=True"
    )
    try:
        async with aconnect_sse(
            httpx_client, "POST", f"{agent_server_origin}/run_sse", json=request
        ) as event_source:
            if event_source.response.status_code != 200:
                await event_source.response.aread()
                logger.error(
                    f"Error from agent server: {event_source.response.status_code} - {event_source.response.text}"
                )
                yield {
                    "author": agent_name,
                    "content": {
                        "parts": [
                            {
                                "text": f"❌ Server Error: {event_source.response.status_code}"
                            }
                        ]
                    },
                }
                return

            async for server_event in event_source.aiter_sse():
                try:
                    event = server_event.json()
                    yield event
                except Exception as e:
                    logger.error(f"Failed to parse SSE event: {e}")
    except Exception as e:
        logger.error(f"SSE connection failed: {e}")
        yield {
            "author": agent_name,
            "content": {"parts": [{"text": f"❌ Connection Failed: {e}"}]},
        }


def extract_all_text(event_obj: dict[str, Any]) -> list[str]:
    """Targeted extraction of text from ADK event content parts."""
    if not isinstance(event_obj, dict):
        return []
    texts = []
    content = event_obj.get("content")
    if isinstance(content, dict):
        parts = content.get("parts")
        if isinstance(parts, list):
            for part in parts:
                if not isinstance(part, dict):
                    continue
                if "text" in part:
                    texts.append(part["text"])
                elif "inlineData" in part:
                    inline_data = part["inlineData"]
                    if isinstance(inline_data, dict):
                        metadata = inline_data.get("metadata", {})
                        if metadata.get("mimeType") == "application/json+a2ui":
                            data = inline_data.get("data")
                            if data:
                                if isinstance(data, dict):
                                    if "components" in data or (
                                        isinstance(data.get("message"), dict)
                                        and "components" in data["message"]
                                    ):
                                        json_str = json.dumps(data)
                                    elif "type" in data:
                                        json_str = json.dumps({"components": [data]})
                                    else:
                                        json_str = json.dumps(data)
                                else:
                                    json_str = json.dumps(data)
                                texts.append(f"<a2ui-json>{json_str}</a2ui-json>")
    return texts


def merge_strings(existing: str, incoming: str) -> str:
    """A truly robust greedy overlap deduplicator."""
    if not existing:
        return incoming
    if not incoming:
        return existing
    e_norm = existing.rstrip()
    i_norm = incoming.lstrip()
    if not i_norm:
        return existing
    max_overlap = min(len(e_norm), len(i_norm), 500)
    for size in range(max_overlap, 0, -1):
        if e_norm.endswith(i_norm[:size]):
            norm_prefix = i_norm[:size]
            idx = incoming.find(norm_prefix)
            return existing + incoming[idx + size :]
    return existing + incoming


def cleanup_final_text(text: str) -> str:
    """Surgical cleanup for known progress messages or system leaks."""
    # Remove progress messages
    text = re.sub(r"🚀\s*Starting the course creation pipeline\.\.\.", "", text)
    text = re.sub(r"✍️\s*Building the final course content\.\.\.", "", text)
    text = re.sub(r"🔍\s*Research is starting\.\.\.", "", text)
    text = re.sub(r"⚖️\s*Judge is evaluating findings\.\.\.", "", text)

    # Remove system author markers if any leaked
    text = re.sub(r"\[progress_.*\]\s*said:?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[capture_.*\]\s*said:?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"For context:?", "", text, flags=re.IGNORECASE)

    # Remove finding markers if they leaked
    text = text.replace("RESEARCH_FINDINGS_START", "").replace(
        "RESEARCH_FINDINGS_END", ""
    )

    # Deduplicate exact <a2ui-json> blocks
    seen_a2ui = set()

    def deduplicate_a2ui(match):
        full_block = match.group(0)
        content = match.group(1).strip()
        if content in seen_a2ui:
            return ""
        seen_a2ui.add(content)
        return full_block

    text = re.sub(r"<a2ui-json>([\s\S]*?)</a2ui-json>", deduplicate_a2ui, text)

    return text.strip()


class SimpleChatRequest(BaseModel):
    message: str
    user_id: str = "test_user"
    session_id: str | None = None
    server_url: str | None = None


@app.get("/api/config")
async def get_config():
    """Expose some environment variables to the frontend."""
    return {
        "agent_server_url": os.getenv("AGENT_SERVER_URL"),
        "mcp_server_url": os.getenv("MCP_SERVER_URL"),
    }


@app.post("/api/chat_stream")
async def chat_stream(request: SimpleChatRequest):
    """Streaming chat endpoint using A2A client."""
    target_server_url = request.server_url or agent_server_url
    if not target_server_url:
        return {
            "error": "AGENT_SERVER_URL environment variable not set, and no server_url provided in request"
        }

    # Ensure trailing slash is removed
    target_server_url = target_server_url.rstrip("/")

    # In A2A, we directly use the session_id as the context_id. If none provided, we pass None.
    context_id = request.session_id or None

    def parse_a2a_parts(parts) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        parts_list = []
        progress_yields = []
        for part in parts:
            inner_part = part.root if hasattr(part, "root") else part
            part_kind = getattr(inner_part, "kind", None)

            if part_kind == "text":
                txt = getattr(inner_part, "text", "")
                parts_list.append({"text": txt})
            elif part_kind == "data":
                data_content = getattr(inner_part, "data", None)
                metadata = getattr(inner_part, "metadata", {}) or {}
                parts_list.append(
                    {"inlineData": {"metadata": metadata, "data": data_content}}
                )

                # Handle tool calls/responses as progress
                adk_type = metadata.get("adk_type")
                if adk_type == "function_call" and isinstance(data_content, dict):
                    tool_name = data_content.get("name", "tool")
                    progress_yields.append(
                        {
                            "type": "progress",
                            "text": f"🛠️ Calling {tool_name}...",
                        }
                    )
                elif adk_type == "function_response" and isinstance(data_content, dict):
                    tool_name = data_content.get("name", "tool")
                    progress_yields.append(
                        {
                            "type": "progress",
                            "text": f"✅ {tool_name} returned rate data",
                        }
                    )
        return parts_list, progress_yields

    def parse_a2a_message(
        message_obj,
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        author = getattr(message_obj, "role", "agent")
        if hasattr(author, "value"):
            author = author.value
        parts = getattr(message_obj, "parts", []) or []
        parts_list, progress_yields = parse_a2a_parts(parts)
        return author, parts_list, progress_yields

    async def event_generator():
        final_text = ""
        logger.info(f"Starting A2A event generator for context {context_id}")

        # Initial heartbeat
        yield (
            json.dumps(
                {
                    "type": "progress",
                    "text": "🚀 Connecting to A2A backend...",
                }
            )
            + "\n"
        )

        try:
            a2a_client = await get_a2a_client(target_server_url)

            # Construct the Message object
            import uuid

            msg_id = uuid.uuid4().hex
            parts = [A2APart(A2ATextPart(kind="text", text=request.message))]
            a2a_msg = A2AMessage(
                role=A2ARole.user,
                message_id=msg_id,
                parts=parts,
                context_id=context_id,
            )

            params = MessageSendParams(message=a2a_msg)
            rpc_request = SendStreamingMessageRequest(
                id=uuid.uuid4().hex,
                params=params,
            )

            # Run stream
            async for chunk in a2a_client.send_message_streaming(rpc_request):
                if not chunk or not chunk.root:
                    continue

                # Check for JSON-RPC error
                if hasattr(chunk.root, "error") and chunk.root.error:
                    error_msg = chunk.root.error.message
                    yield (
                        json.dumps(
                            {
                                "type": "progress",
                                "text": f"❌ Error: {error_msg}",
                            }
                        )
                        + "\n"
                    )
                    continue

                if not hasattr(chunk.root, "result") or not chunk.root.result:
                    continue

                res = chunk.root.result
                kind = getattr(res, "kind", None)
                logger.info(
                    f"A2A Chunk received. Kind: {kind}, Result Type: {type(res)}, Data: {res}"
                )

                if kind == "message":
                    author, parts_list, prog_yields = parse_a2a_message(res)
                    for py in prog_yields:
                        yield json.dumps(py) + "\n"

                    mapped_event = {"author": author, "content": {"parts": parts_list}}

                    event_text = "".join(extract_all_text(mapped_event))
                    if event_text:
                        yield (
                            json.dumps(
                                {
                                    "type": "progress",
                                    "text": f"💬 {author}: {event_text[:50]}...",
                                }
                            )
                            + "\n"
                        )
                        if author != "user":
                            final_text += event_text

                elif kind == "status-update":
                    # Status updates represent progress
                    status_obj = getattr(res, "status", None)
                    status_state = (
                        getattr(status_obj, "state", "running")
                        if status_obj
                        else "running"
                    )
                    if hasattr(status_state, "value"):
                        status_state = status_state.value
                    yield (
                        json.dumps(
                            {
                                "type": "progress",
                                "text": f"⚙️ Agent State: {status_state}...",
                            }
                        )
                        + "\n"
                    )

                    # Extract content parts if a nested message is present in the status
                    status_message = (
                        getattr(status_obj, "message", None) if status_obj else None
                    )
                    if status_message:
                        author, parts_list, prog_yields = parse_a2a_message(
                            status_message
                        )
                        for py in prog_yields:
                            yield json.dumps(py) + "\n"

                        mapped_event = {
                            "author": author,
                            "content": {"parts": parts_list},
                        }
                        event_text = "".join(extract_all_text(mapped_event))
                        if event_text:
                            yield (
                                json.dumps(
                                    {
                                        "type": "progress",
                                        "text": f"💬 {author}: {event_text[:50]}...",
                                    }
                                )
                                + "\n"
                            )
                            if author != "user":
                                final_text += event_text

                elif kind == "artifact-update":
                    artifact_obj = getattr(res, "artifact", None)
                    if artifact_obj:
                        parts = getattr(artifact_obj, "parts", []) or []
                        parts_list, prog_yields = parse_a2a_parts(parts)
                        for py in prog_yields:
                            yield json.dumps(py) + "\n"

                        mapped_event = {
                            "author": "agent",
                            "content": {"parts": parts_list},
                        }
                        event_text = "".join(extract_all_text(mapped_event))
                        if event_text:
                            yield (
                                json.dumps(
                                    {
                                        "type": "progress",
                                        "text": f"🎨 Visual Update: {event_text[:50]}...",
                                    }
                                )
                                + "\n"
                            )
                            final_text += event_text

        except Exception as e:
            logger.exception("A2A streaming failed")
            yield (
                json.dumps(
                    {
                        "type": "progress",
                        "text": f"❌ Connection Failed: {e}",
                    }
                )
                + "\n"
            )

        # Clean final text from duplicate lines if needed
        final_text = cleanup_final_text(final_text)
        logger.info(f"A2A Stream complete. Final text length: {len(final_text)}")
        yield json.dumps({"type": "result", "text": final_text}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@app.get("/health")
async def health():
    return {"status": "ok"}


# Mount frontend from the Vite build directory
frontend_path = os.path.join(os.path.dirname(__file__), "dist")
if not os.path.exists(frontend_path):
    # For local development we might not have dist, but for Cloud Run we MUST
    if os.getenv("K_SERVICE"):
        raise RuntimeError(
            f"Frontend directory not found at {frontend_path}. Check Docker build."
        )
    else:
        print(f"Warning: Frontend directory not found at {frontend_path}")
else:
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8080))
    print(f"Starting server on port {port}")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_config=get_uvicorn_log_config(os.getenv("LOG_LEVEL", "info")),
    )
