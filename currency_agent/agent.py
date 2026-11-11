import logging
import os
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

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from starlette.responses import JSONResponse


# A2UI 1.0 imports
from a2ui.adk import SendA2uiToClientToolset
from a2ui.adk.a2a import A2uiPartConverter
from a2ui.core.basic_catalog import BasicCatalog
from a2ui.core.schema import AgentToRendererMessage
from a2ui.processor import A2uiRequestProcessor
from a2ui.transformers.macros import MacroExpander
from a2ui.utils import validate_payload
from pydantic import TypeAdapter
from google.adk.a2a.executor.a2a_agent_executor import (
    A2aAgentExecutor,
    A2aAgentExecutorConfig,
)

from currency_agent.macros import CHARTS_CATALOG, MACROS

logger = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s]: %(message)s", level=logging.INFO)

load_dotenv()

# --- A2UI 1.0 setup ---------------------------------------------------------
# Transport catalogs: what the renderer implements (Basic 1.0 + currency charts).
BASE_CATALOGS = [BasicCatalog("1.0"), CHARTS_CATALOG]

# Server-side macros: the model sees RateCard(...) / RateHistoryChart(...) as
# components; the expander runs them here and sends flat catalog components.
macro_expander = MacroExpander(MACROS, on_error="raise")
INFERENCE_CATALOGS = macro_expander.transform_catalogs(BASE_CATALOGS)

# A2uiRequestProcessor uses the A2UI Express inference format by default.
a2ui_processor = A2uiRequestProcessor(catalogs=INFERENCE_CATALOGS)

ROLE_INSTRUCTION = (
    "You are a specialized assistant for currency conversions. "
    "Use the 'get_exchange_rate' tool to answer questions about currency exchange rates. "
    "If the user asks about anything other than currency conversion or exchange rates, "
    "politely state that you cannot help with that topic and can only assist with currency-related queries. "
    "Do not attempt to answer unrelated questions or use tools for other purposes.\n\n"
    "Show results as A2UI. Prefer the server-side macros: RateCard for a rate or a "
    "conversion, RateHistoryChart for trends or history over time. These macros look "
    "up the figures on the server, so pass only currency codes and the amount or day "
    "count. Use Basic catalog components (Card, Column, Row, Text) or BarChart only "
    "for layouts the macros do not cover, such as comparing several currencies."
)

_message_adapter: TypeAdapter[AgentToRendererMessage] = TypeAdapter(
    AgentToRendererMessage
)


class MacroSendA2uiToClientToolset(SendA2uiToClientToolset):
    """SendA2uiToClientToolset that expands A2UI 1.0 server-side macros.

    The stock tool compiles the model's Express payload and validates it
    against the inference catalogs (which include the macro sidecar). This
    subclass then runs the macros and re-validates the expanded messages against
    the catalogs the renderer actually implements.
    """

    class _MacroTool(SendA2uiToClientToolset._SendA2uiJsonToClientTool):
        def _parse_payload(self, processor, payload):
            messages = super()._parse_payload(processor, payload)
            typed = [_message_adapter.validate_python(m) for m in messages]
            expanded = macro_expander.transform_to_transport(typed)
            wire = [
                m.model_dump(by_alias=True, exclude_none=True) for m in expanded
            ]
            validate_payload(BASE_CATALOGS, wire)
            return wire

    def __init__(self, a2ui_enabled, a2ui_processor):
        super().__init__(a2ui_enabled=a2ui_enabled, a2ui_processor=a2ui_processor)
        self._ui_tool = self._MacroTool(a2ui_processor)
        self._ui_tools = [self._ui_tool]


logger.info("--- 🤖 Creating ADK Currency Agent (A2UI 1.0, Express + macros) ---")
logger.info(f"MCP_SERVER_URL: {os.getenv('MCP_SERVER_URL')}")

# The toolset appends the processor's Express prompt snippet to the instruction.
a2ui_toolset = MacroSendA2uiToClientToolset(
    a2ui_enabled=True,
    a2ui_processor=a2ui_processor,
)

root_agent = LlmAgent(
    model=os.getenv("GENAI_MODEL", "gemini-2.5-flash"),
    name="currency_agent",
    description="An agent that can help with currency conversions",
    instruction=ROLE_INSTRUCTION,
    tools=[
        a2ui_toolset,
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8080/mcp")
            ),
        ),
    ],
)


# Make the agent A2A-compatible and configure it to use the A2UI part converter
def agent_executor_factory(runner):
    config = A2aAgentExecutorConfig(
        gen_ai_part_converter=A2uiPartConverter(
            a2ui_processor, bypass_tool_check=True
        ).convert
    )
    return A2aAgentExecutor(runner=runner, config=config)


from google.adk.a2a.utils.agent_card_builder import AgentCardBuilder
from a2a.types import AgentCapabilities

# Monkeypatch AgentCardBuilder to always enable streaming capability
if not hasattr(AgentCardBuilder, "_original_init"):
    AgentCardBuilder._original_init = AgentCardBuilder.__init__

    def _patched_init(self, *args, **kwargs):
        if "capabilities" not in kwargs or kwargs["capabilities"] is None:
            kwargs["capabilities"] = AgentCapabilities(streaming=True)
        else:
            kwargs["capabilities"].streaming = True
        AgentCardBuilder._original_init(self, *args, **kwargs)

    AgentCardBuilder.__init__ = _patched_init

a2a_app = to_a2a(
    root_agent,
    host=os.getenv("HOST", "127.0.0.1"),
    port=int(os.getenv("PORT", 10000)),
    agent_executor_factory=agent_executor_factory,
)


async def health(request):
    return JSONResponse({"status": "ok"})


a2a_app.add_route("/health", health, methods=["GET"])
