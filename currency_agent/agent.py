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


# A2UI imports
from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.adk.send_a2ui_to_client_toolset import (
    SendA2uiToClientToolset,
    A2uiPartConverter,
)
from google.adk.a2a.executor.a2a_agent_executor import (
    A2aAgentExecutor,
    A2aAgentExecutorConfig,
)

logger = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s]: %(message)s", level=logging.INFO)

load_dotenv()

from a2ui.schema.catalog import CatalogConfig

# Set up A2UI schema manager and catalogs
schema_manager = A2uiSchemaManager(
    version="0.9",
    catalogs=[
        BasicCatalog.get_config("0.9"),
        CatalogConfig.from_path(
            name="currency-charts",
            catalog_path=os.path.join(os.path.dirname(__file__), "custom_catalog.json"),
        ),
    ],
)
selected_catalog = schema_manager.get_selected_catalog()
examples_str = schema_manager.load_examples(selected_catalog)

# Generate system prompt instruction with A2UI component catalog schema and examples
SYSTEM_INSTRUCTION = schema_manager.generate_system_prompt(
    role_description=(
        "You are a specialized assistant for currency conversions. "
        "Your sole purpose is to use the 'get_exchange_rate' tool to answer questions about currency exchange rates. "
        "If the user asks about anything other than currency conversion or exchange rates, "
        "politely state that you cannot help with that topic and can only assist with currency-related queries. "
        "Do not attempt to answer unrelated questions or use tools for other purposes."
    ),
    workflow_description="Use components to display structured currency conversions and rates.",
    ui_description="Use Card and Text components for displaying rates. Use Table components for tabular data. Use BarChart components or LineChart components when presenting exchange rate trends or histories over time.",
    include_schema=True,
    include_examples=True,
    allowed_components=["Card", "Text", "Table", "BarChart", "LineChart"],
)

logger.info("--- 🤖 Creating ADK Currency Agent... ---")
logger.info(f"MCP_SERVER_URL: {os.getenv('MCP_SERVER_URL')}")

a2ui_toolset = SendA2uiToClientToolset(
    a2ui_enabled=True,
    a2ui_catalog=selected_catalog,
    a2ui_examples=examples_str,
)

root_agent = LlmAgent(
    model=os.getenv("GENAI_MODEL", "gemini-2.5-flash"),
    name="currency_agent",
    description="An agent that can help with currency conversions",
    instruction=SYSTEM_INSTRUCTION,
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
            selected_catalog, bypass_tool_check=True
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
