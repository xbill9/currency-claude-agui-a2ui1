# Currency Agent Architecture & Protocols (with A2UI)

Below is a visual flow of interactions between the user-facing workspace frontend, the A2A-wrapped ADK agent, the Gemini LLM, the local Model Context Protocol (MCP) server, and the external data source:

![Architecture Diagram](/home/xbill/currency-agent/images/architecture_diagram_a2ui.png)

## Architecture Diagram (Mermaid)

Below is the Mermaid flowchart representation of the architecture:

```mermaid
graph TD
    %% Styling
    classDef client fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1;
    classDef agent fill:#f1f8e9,stroke:#558b2f,stroke-width:2px,color:#33691e;
    classDef llm fill:#ede7f6,stroke:#651fff,stroke-width:2px,color:#4a148c;
    classDef mcp fill:#fff3e0,stroke:#ef6c00,stroke-width:2px,color:#e65100;
    classDef external fill:#fafafa,stroke:#9e9e9e,stroke-width:2px,color:#212121;
    classDef ui fill:#f3e5f5,stroke:#8e24aa,stroke-width:2px,color:#7b1fa2;

    %% Nodes
    Browser["User Web Browser<br/>(Currency Intellect Frontend)"]:::client
    A2UIEngine["A2UI Rendering Engine<br/>(renderA2UI in app.ts)"]:::ui
    FrontendServer["Frontend Web Server<br/>(frontend/main.py)"]:::client
    AgentServer["A2A Agent Server<br/>(currency_agent/agent.py)"]:::agent
    A2UISchema["A2UI Schema Manager<br/>& Part Converter"]:::ui
    Gemini["Google Gemini API<br/>(gemini-2.5-flash)"]:::llm
    MCPServer["MCP Server<br/>(mcp-server/server.py)"]:::mcp
    FrankAPI["Frankfurter API<br/>(api.frankfurter.dev)"]:::external

    %% Connections and Protocols
    Browser -->|1. User queries| FrontendServer
    FrontendServer -->|2. A2A Protocol / HTTP<br/>(Port 10000)| AgentServer
    AgentServer -->|3. Gemini API / HTTPS<br/>(With A2UI instructions)| Gemini
    AgentServer -->|4. Model Context Protocol / SSE<br/>(Port 8080 / /mcp)| MCPServer
    MCPServer -->|5. HTTP REST / JSON| FrankAPI

    %% Response cycle
    FrankAPI -.->|Rates JSON| MCPServer
    MCPServer -.->|Tool Output| AgentServer
    AgentServer -.->|Updated Context| Gemini
    Gemini -.->|6. Text response with A2UI block| AgentServer
    AgentServer -.->|7. A2UI Part Conversion| FrontendServer
    FrontendServer -.->|8. Delivery to Browser| Browser
    Browser -->|9. Pass JSON to engine| A2UIEngine
    A2UIEngine -.->|10. Render dynamic cards/tables| Browser

    subgraph Frontend Application
        Browser
        A2UIEngine
    end

    subgraph ADK Agent Ecosystem
        AgentServer
        A2UISchema
    end

    subgraph Model Context Protocol
        MCPServer
    end
```

---

## Detailed Components & Protocols

### 1. Agent-to-Agent (A2A) Protocol
*   **Source:** [main.py](file:///home/xbill/currency-agent/frontend/main.py)
*   **Destination:** [agent.py](file:///home/xbill/currency-agent/currency_agent/agent.py)
*   **Port:** Default `10000` (or `8080` in Cloud Run env)
*   **Protocol Details:** 
    *   Uses the **A2A Python SDK** (`a2a-sdk`).
    *   Uses standard HTTP endpoints to register, exchange, and resolve agent metadata cards.
    *   Implements `SendMessageRequest`, asynchronous task generation (`Task` object), and status polling (`GetTaskRequest`).
    *   Enables multi-turn conversational context (`contextId` propagation).

### 2. Google Gemini API Protocol
*   **Source:** [agent.py](file:///home/xbill/currency-agent/currency_agent/agent.py) (via Google ADK `LlmAgent`)
*   **Destination:** Google GenAI Gemini endpoint (or Vertex AI APIs)
*   **Protocol Details:**
    *   Secured via `GOOGLE_API_KEY` (Gemini API) or Google Cloud Service Account credentials (Vertex AI).
    *   Uses standard HTTPS JSON payloads.
    *   Communicates model instructions, user prompts, conversation history, and handles function/tool-calling schemas returned by the model.
    *   The primary model used is `gemini-2.5-flash`.

### 3. Model Context Protocol (MCP)
*   **Source:** [agent.py](file:///home/xbill/currency-agent/currency_agent/agent.py) (via `McpToolset` / `StreamableHTTPConnectionParams`)
*   **Destination:** [server.py](file:///home/xbill/currency-agent/mcp-server/server.py)
*   **Port:** Default `8080` (endpoint `/mcp`)
*   **Protocol Details:**
    *   Standardizes tool exposure and execution schema under the **Model Context Protocol** spec.
    *   Communicates over HTTP using Server-Sent Events (SSE) or simple HTTP SSE streams.
    *   The MCP Server advertises the available tool (`get_exchange_rate`) and receives tool execution requests containing parameters (e.g. `currency_from`, `currency_to`, `currency_date`).

### 4. HTTP REST/JSON API Protocol
*   **Source:** [server.py](file:///home/xbill/currency-agent/mcp-server/server.py)
*   **Destination:** Frankfurter API (`https://api.frankfurter.dev`)
*   **Protocol Details:**
    *   Standard HTTP GET request using `httpx`.
    *   Fetches real-time market data in standard JSON format containing exchange rates.

### 5. Agent-to-UI (A2UI) Protocol & Integration
*   **Source:** `a2ui` package & [agent.py](file:///home/xbill/currency-agent/currency_agent/agent.py) (via `SendA2uiToClientToolset`, `A2uiPartConverter`)
*   **Destination:** [app.ts](file:///home/xbill/currency-agent/frontend/frontend/app.ts) (runs in user's browser)
*   **Protocol Details:**
    *   Defines standard JSON schemas for rich, interactive, and responsive UI components (e.g. Cards, Tables, Text fields, Columns, Rows).
    *   The `A2uiSchemaManager` generates system prompt instructions, catalogs, and examples instructing the LLM on component schemas.
    *   The LLM generates structured layout descriptions wrapped in `<a2ui-json>` elements.
    *   The frontend client parses responses via regex for `<a2ui-json>...</a2ui-json>`, then uses the `renderA2UI()` engine to map JSON components directly to glassmorphic, stylized HTML container elements.

