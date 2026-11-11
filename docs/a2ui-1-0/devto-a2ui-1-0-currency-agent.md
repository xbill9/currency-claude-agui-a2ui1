---
title: "A2UI 1.0 in a Currency Agent: One Message per Surface, Mixed Catalogs and Server-Side Macros"
published: false
description: "A Google ADK currency agent moves from A2UI 0.9 to A2UI 1.0: what changed in the protocol, what 1.0 can do that 0.9 could not, and how server-side macros let the model write one line while the server fills in the rates."
tags: a2ui, agents, gemini, react
cover_image: https://raw.githubusercontent.com/xbill9/currency-claude-agui-a2ui1/main/docs/a2ui-1-0/devto-cover.b6f0e686.jpg
---

This article provides a step by step guide to a currency agent that answers with generated UI on A2UI 1.0. A Google ADK agent on Gemini looks up exchange rates, describes its answer as A2UI components, and a Next.js CopilotKit front end renders the cards and charts over AG-UI. It covers what changed from the A2UI 0.9 build to this one, what changed in the protocol, and what 1.0 adds.

https://github.com/xbill9/currency-claude-agui-a2ui1

**On A2UI 1.0 the model writes one line, and the server fills in the numbers.** For "Convert 100 USD to EUR" the model's whole UI is `root = RateCard("USD", "EUR", 100)`. A server-side macro fetches the rate from the Frankfurter API, expands the line into six Basic catalog components, and the browser receives them in a single `createSurface` message. On the 0.9 build the model called the rate tool, read the result, and typed every figure into the component JSON. Ten prompts, run ten times each, rendered cleanly in 100 of 100 replies on `gemini-3.8-flash` and 100 of 100 on `gemini-2.5-flash`.

---

#### What Is Being Built?

![Architecture: the browser talks AG-UI to a bridge on port 8008, A2A clients talk to a server on port 10000, both run the same ADK agent, which calls the MCP server on port 8080 and the Frankfurter API](https://raw.githubusercontent.com/xbill9/currency-claude-agui-a2ui1/main/docs/a2ui-1-0/img/architecture.png)

| Service | Port | Code |
| :--- | :--- | :--- |
| React UI: Next.js, CopilotKit, `@a2ui/react` | 3000 | `frontend-react/` |
| AG-UI bridge: the ADK agent in-process | 8008 | `frontend-react/agent/` |
| A2A server: the same ADK agent over A2A | 10000 | `currency_agent/` |
| MCP server: `get_exchange_rate` (FastMCP) | 8080, path `/mcp` | `mcp-server/` |

Next.js forwards `/api/copilotkit` to the AG-UI bridge, which imports the ADK agent and streams AG-UI events back. The A2A server runs the same agent object for A2A clients, and Cloud Build deploys it to Cloud Run.

Versions, read from the machine on 2026-11-11:

| Component | Version |
| :--- | :--- |
| `a2ui-agent-sdk` / `a2ui-adk` / `a2ui-core` | 0.11.0 / 0.3.0 / 0.6.0 |
| `@a2ui/react` / `@a2ui/web_core` | 0.15.0 / 0.15.0 |
| `google-adk` / `ag_ui_adk` / `a2a-sdk` | 2.13.0 / 0.6.5 / 0.3.26 |
| `next` / `react` / `@copilotkit/react-core` | 16.1.1 / 19.2.7 / 1.56.4 |
| Python / Node | 3.14.7 / v24.21.0 |
| Model | `gemini-3.8-flash` (default), `gemini-2.5-flash` |

---

#### From the Last Build to This One

![Before and after: on A2UI 0.9 the model calls the rate tool and writes the component JSON with the figures, the reply text carries a2ui-json blocks, and the browser cuts them out and repairs them; on A2UI 1.0 the model writes one macro call, the server compiles and validates it, the macro fetches the rate, the result is validated again and arrives as a tool result](https://raw.githubusercontent.com/xbill9/currency-claude-agui-a2ui1/main/docs/a2ui-1-0/img/before-after.png)

| | Last build: A2UI 0.9 | This build: A2UI 1.0 |
| :--- | :--- | :--- |
| Agent library | `a2ui-agent-sdk` 0.2.1, `A2uiSchemaManager(version="0.9")` | `a2ui-agent-sdk` 0.11.0, `a2ui-adk` 0.3.0, `a2ui-core` 0.6.0 |
| Model output | Component JSON with the figures in it | An Express `<a2ui>` block, usually one macro call |
| Rate figures | Typed by the model from the MCP result | Fetched by a macro on the server |
| Comparisons | Several rate-tool calls, then model-typed values | One `RateComparison` call |
| How the UI travels | `<a2ui-json>` blocks in the reply text | `validated_a2ui_json` in the tool result |
| A2UI written as reply text | Parsed out of the text in the browser | Sent through the UI tool on the server |
| Validation | A browser normalizer accepts several shapes | The server validates before and after macro expansion |
| Renderer | `@copilotkit/a2ui-renderer` with CopilotKit's A2UI middleware | `@a2ui/react` 0.15.0 |
| Charts catalog id | `https://a2ui.org/catalog/currency-charts` | `https://a2ui.org/catalog/currency-charts/v1/catalog.json`, `protocolVersion` 1.0 |
| `page.tsx` | 309 lines | 150 lines |

---

#### What Changed in the A2UI 1.0 Protocol?

Read from the installed `a2ui-core` 0.6.0, which ships the 0.9 and 1.0 schemas side by side:

| | A2UI 0.9 | A2UI 1.0 |
| :--- | :--- | :--- |
| Version string | `"v0.9"` | `"1.0"` |
| Agent → renderer | createSurface, updateComponents, updateDataModel, deleteSurface | the same four, plus callRendererFunction and agentFunctionResponse |
| Renderer → agent | action, error | action, error, plus callAgentFunction and rendererFunctionResponse |
| `createSurface` | catalog id, `theme`, `sendDataModel` | inline `components` and `dataModel`, `sendDataModel`, `metadata`; no `theme` |
| Bindings and calls | `{"path": ...}`, `{"call": ...}` | `{"@path": ...}`, `{"@call": ...}` |
| Text variants | h1, h2, h3, h4, h5, caption, body | caption, body; headings come from Markdown |
| Basic catalog | 18 components, 14 functions | the same 18 components, 15 functions (adds `@index`) |
| Names | client and server | renderer and agent |

The Basic catalog's components are the same in both versions: AudioPlayer, Button, Card, CheckBox, ChoicePicker, Column, DateTimeInput, Divider, Icon, Image, List, Modal, Row, Slider, Tabs, Text, TextField and Video. Their properties moved: TextField gains `placeholder` and replaces `validationRegexp` with a `regex` check, Slider gains `steps`, and Video gains `posterUrl`.

---

#### What Can A2UI 1.0 Do That 0.9 Could Not?

- **A whole surface in one message.** `createSurface` carries the components and the data model inline, so a new surface needs one message.
- **Several catalogs on one surface.** Each component can name its own `catalogId`, overriding the surface default.
- **Functions in both directions.** The agent can call a renderer function (`callRendererFunction`) and the renderer can call an agent function (`callAgentFunction`), each with its own response message.
- **Function permissions.** A catalog marks each function `rendererOnly`, `agentOnly` or `rendererOrAgent`, and can require a user gesture with `requiresUserActivation`.
- **Composition rules.** A catalog can list `allowedParents` and `allowedChildren` per component, and the renderer reports violations with the new error codes `UNALLOWED_PARENT` and `UNALLOWED_CHILD`.
- **Graded validation.** Checks return a validation result with a `severity` of error, warning or info.
- **Actions that speak.** A button's action can carry a `userMessage`, which travels with the action to the agent.
- **Accessibility.** Components take `live` (off, polite, assertive) and `hidden`.
- **List positions.** The `@index` function returns an item's position inside a list template.
- **Extensions.** Components, surfaces, actions and catalogs carry `metadata.extensions` for custom data.
- **Catalog instructions.** A catalog definition can carry Markdown `instructions` for the model.

---

#### At This Point You Should Have…

- Python 3.13 or newer and Node.js with npm
- A Gemini API key from Google AI Studio, or a Google Cloud project with Vertex AI enabled
- The repository cloned:

```shell
git clone https://github.com/xbill9/currency-claude-agui-a2ui1.git
cd currency-claude-agui-a2ui1
```

---

#### Step 1 — Install and Configure

```shell
make install
echo "GOOGLE_API_KEY=<your_api_key_here>" >> .env
echo "GOOGLE_GENAI_USE_VERTEXAI=FALSE" >> .env
```

`make install` runs `uv sync` and `npm install` for both front ends. The agent uses `gemini-3.8-flash` unless `GENAI_MODEL` is set in `.env`.

---

#### Step 2 — Start the Stack

```shell
make start
curl -s http://127.0.0.1:10000/health
curl -s http://127.0.0.1:8008/health
```

```text
{"status":"ok"}
{"status":"ok"}
```

`make start` launches the MCP server, the A2A server, the AG-UI bridge and the Next.js dev server in the background. The UI is at http://localhost:3000.

---

#### Step 3 — Express: What the Model Writes

Express is the inference format in `a2ui-agent-sdk`: a short Python-like language inside `<a2ui>` tags that the server compiles into A2UI messages. `$/path` is a binding, `?required` is a check, and `root =` names the top component. The same block compiles to either protocol version:

```text
surface("main")
$/user/name = "Ada"
title = Text(formatString("Hello ${/user/name}"))
btn = Button(Text("Save"), action=Event("save", {name: $/user/name}, userMessage="Saving"))
root = Column([title, TextField("Name", $/user/name, checks=[?required("Name is required")]), btn])
```

```shell
python3 docs/a2ui-1-0/tools/express_0_9_vs_1_0.py
```

```text
## A2UI 1.0: 1 message(s): ['createSurface']
## A2UI 0.9 (userMessage removed): 3 message(s): ['createSurface', 'updateComponents', 'updateDataModel']
## userMessage on 0.9
ExpressValidationError: Event userMessage requires protocol v1.0 or later; the target version v0.9 has no userMessage field.
```

On 1.0 the text field's value is `{"@path": "/user/name"}` and its check is `{"@call": "required", ...}`, all inside the one `createSurface` along with `"dataModel": {"user": {"name": "Ada"}}`.

---

#### Step 4 — Server-Side Macros: The Model Writes One Line

A macro is a Python function the model calls like a component. `@macro` turns its type hints and docstring into a catalog entry, and at send time `MacroExpander` runs it and replaces it with Basic catalog components, so the browser needs no macro support. The macros live in `currency_agent/macros.py`:

```python
@macro
def RateCard(currency_from: str, currency_to: str, amount: float = 1.0) -> Card:
    """Card with the live exchange rate and a converted amount. The server looks
    up the rate, so do not pass rate figures.
    """
    src, dst = _code(currency_from), _code(currency_to)
    data = _get("latest", **{"from": src, "to": dst})
    rate = data["rates"][dst]
    return Card(
        child=Column(
            children=[
                Text(text=f"### {amount:,.2f} {src} = {amount * rate:,.2f} {dst}"),
                Text(text=f"1 {src} = {rate:.5f} {dst}"),
                Divider(),
                Text(
                    text=f"ECB reference rate for {data['date']} (Frankfurter API)",
                    variant="caption",
                ),
            ]
        )
    )
```

`_code()` accepts only a three-letter currency code, and the day counts are clamped to 7–365, because the arguments come from the model.

For "Convert 100 USD to EUR please." the model's whole tool call was:

```text
send_a2ui_json_to_client:
<a2ui>
surface("conversion")
root = RateCard("USD", "EUR", 100)
</a2ui>
```

What reached the browser:

```text
version 1.0, ['createSurface'], 6 components
  https://a2ui.org/specification/v1_0/catalogs/basic/catalog.json: ['Text', 'Text', 'Divider', 'Text', 'Column', 'Card']
  Text: ### 100.00 USD = 89.87 EUR
  Text: 1 USD = 0.89871 EUR
  Text: ECB reference rate for 2026-11-11 (Frankfurter API)
```

The agent validates twice in `currency_agent/agent.py`: once against the catalogs the model sees, which include the macros, and again after expansion against the catalogs the browser implements:

```python
def _parse_payload(self, processor, payload):
    messages = super()._parse_payload(processor, payload)
    typed = [_message_adapter.validate_python(m) for m in messages]
    expanded = macro_expander.transform_to_transport(typed)
    wire = [m.model_dump(by_alias=True, exclude_none=True) for m in expanded]
    validate_payload(BASE_CATALOGS, wire)
    return wire
```

---

#### Step 5 — Two Catalogs on One Surface

The browser implements two catalogs: Basic 1.0 and a currency charts catalog with `LineChart` and `BarChart`. For "Show me EUR to USD for the past 6 months and the current rate" the model wrote two macro calls:

```text
<a2ui>
surface("main")
root = Column([rateCard, historyChart])
rateCard = RateCard("EUR", "USD")
historyChart = RateHistoryChart("EUR", "USD", 180)
</a2ui>
```

The browser received one `createSurface` with each component naming its catalog:

```text
version 1.0, ['createSurface'], 12 components
  https://a2ui.org/specification/v1_0/catalogs/basic/catalog.json: ['Column', 'Text', 'Text', 'Divider', 'Text', 'Column', 'Card', 'Text', 'Text', 'Column', 'Card']
  https://a2ui.org/catalog/currency-charts/v1/catalog.json: ['LineChart']
```

![A rate card for EUR to USD above a 180-day line chart](https://raw.githubusercontent.com/xbill9/currency-claude-agui-a2ui1/main/docs/a2ui-1-0/img/card-and-chart.png)

The macros catalog appears only in what the model writes. After expansion, every component belongs to a catalog the browser implements.

---

#### Step 6 — The Browser Renders the Tool Result

The page registers a renderer for the `send_a2ui_json_to_client` tool and hands its result to `@a2ui/react`:

```tsx
useRenderTool(
  {
    name: "send_a2ui_json_to_client",
    render: ({ result }: any) => {
      const messages = extractA2uiMessages(result);
      return messages ? <A2uiMessages messages={messages} /> : null;
    },
  } as any,
  [],
);
```

The charts catalog id, `https://a2ui.org/catalog/currency-charts/v1/catalog.json`, appears in `currency_agent/custom_catalog.json` on the agent and in `A2UICustomCatalog.tsx` in the browser, with matching component props.

---

#### Step 7 — A Rate Card

Ask: **How much is 250 USD in EUR?**

![Rate card: 250.00 USD = 224.68 EUR, 1 USD = 0.89871 EUR, ECB reference rate for 2026-11-11](https://raw.githubusercontent.com/xbill9/currency-claude-agui-a2ui1/main/docs/a2ui-1-0/img/rate-card.png)

Everyday wording works the same way: "What's a thousand euros in dollars?" became `RateCard("EUR", "USD", 1000)` and `1,000.00 EUR = 1,112.70 USD`.

---

#### Step 8 — History Charts

Ask: **Show me the USD to JPY trend over the last 90 days**

![Line chart of USD to JPY from 2026-08-13 to 2026-11-11 with low 153.27, high 160.16 and latest 159.23](https://raw.githubusercontent.com/xbill9/currency-claude-agui-a2ui1/main/docs/a2ui-1-0/img/line-chart.png)

`RateHistoryChart("USD", "JPY", 90)` fetched 65 daily rates and drew them with `LineChart`. The low, high and latest line is computed in the macro.

"How has the British pound done against the euro this year?" became `RateHistoryChart("GBP", "EUR", 365)`, 2025-11-11 to 2026-11-11, with 256 points:

![The full app: the Currency Intellect page on the left and the chat panel on the right with a GBP to EUR chart for the last 365 days](https://raw.githubusercontent.com/xbill9/currency-claude-agui-a2ui1/main/docs/a2ui-1-0/img/full-app.png)

---

#### Step 9 — Comparing Currencies

`RateComparison` fetches today's rate for each currency and the history over a period, in two Frankfurter calls, and charts the percent change. Percent change puts every currency on one scale, yen included:

```python
@macro
def RateComparison(currency_from: str, currencies: list[str], days: int = 30) -> Card:
    """Card comparing several currencies against one base currency: today's rate
    for each, and a bar chart of how much each rate moved over the period, in
    percent. The server looks up every rate, so do not pass rate figures.
    """
```

Ask: **Compare the euro, pound and Swiss franc against the dollar in a bar chart**

```text
send_a2ui_json_to_client:
<a2ui>
surface("main")
root = RateComparison("USD", ["EUR", "GBP", "CHF"])
</a2ui>
```

![1 USD against 3 currencies: today's rates for EUR, GBP and CHF above a bar chart of the change since 2026-10-12, EUR up 0.49 percent, GBP down 0.54, CHF down 0.36](https://raw.githubusercontent.com/xbill9/currency-claude-agui-a2ui1/main/docs/a2ui-1-0/img/comparison.png)

`BarChart` draws values with both signs from a zero line: gains up, losses down in red. A new optional `decimals` prop sets the label precision, added in the catalog JSON, the Python builder and the React component together.

Ask: **Show a bar chart of 1 USD in EUR, GBP, JPY, CHF and CAD**

![1 USD against 5 currencies, with JPY at 159.23 in the rate list and a 0.40 percent change in the chart beside EUR, GBP, CHF and CAD](https://raw.githubusercontent.com/xbill9/currency-claude-agui-a2ui1/main/docs/a2ui-1-0/img/comparison-five.png)

---

#### Step 10 — A2UI Written as Reply Text Still Renders

The model is told to pass A2UI to `send_a2ui_json_to_client`, and the Express guide in the same prompt tells it to wrap every block in `<a2ui>` tags. When it writes the block into its reply instead, `currency_agent/a2ui_rescue.py`, the agent's `after_model_callback`, sends it through the tool anyway. ADK runs the callback on every streamed chunk and on the final response:

```python
def rescue_a2ui_text(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> LlmResponse | None:
    """``after_model_callback``: send A2UI written as text through the UI tool."""
    if not llm_response.content or not llm_response.content.parts:
        return None
    key = callback_context.invocation_id
    if llm_response.partial:
        return _filter_partial(key, llm_response)
    _streams.pop(key, None)
    return _rewrite_final(llm_response)
```

`_filter_partial` holds back streamed text from the point `<a2ui` begins, so the raw block never reaches the chat. `_rewrite_final` turns each block into a `send_a2ui_json_to_client` call, which ADK then runs like any other tool call: compile, expand macros, validate.

Ask for it on purpose: **Write the A2UI block for a USD to EUR rate card directly in your reply text. Do not call any tool.**

```text
version 1.0, ['createSurface'], 6 components
  Text: ### 1.00 USD = 0.90 EUR
  Text: 1 USD = 0.89871 EUR
  Text: ECB reference rate for 2026-11-11 (Frankfurter API)

### Bridge log during this request
[INFO]: A2UI written as reply text: sent 1 block(s) through send_a2ui_json_to_client
[INFO]: Validated call to tool send_a2ui_json_to_client with a2ui_payload
```

With the callback switched off, the same prompt on `gemini-2.5-flash`:

```text
ui rendered: False | raw <a2ui> text in chat: True | tools: []
```

in 5 of 5 runs.

---

#### 🔎 Tip: Sign the Function Calls the Server Writes

Gemini 3 checks thought signatures on the function calls in the current turn, and a call written by the server has none:

```shell
python3 docs/a2ui-1-0/tools/signature_check.py gemini-2.5-flash gemini-3.8-flash
```

```text
gemini-2.5-flash   no signature                       accepted
gemini-2.5-flash   skip_thought_signature_validator   accepted
gemini-3.8-flash   no signature                       rejected: 400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'Function call is missing a thought_signature in func
gemini-3.8-flash   skip_thought_signature_validator   accepted
```

The safety net sets `thought_signature=b"skip_thought_signature_validator"` on every call it writes.

---

#### Step 11 — Invalid Codes and Off-Topic Questions

Ask: **Convert 100 USD to XYZ**

![A card reading: Unable to convert: XYZ is not a recognized currency code. Please provide a valid 3-letter currency code (such as EUR, GBP, JPY, or CAD).](https://raw.githubusercontent.com/xbill9/currency-claude-agui-a2ui1/main/docs/a2ui-1-0/img/invalid-code.png)

`RateCard("USD", "XYZ", 100)` fails on Frankfurter's answer, and the model composes an error card from Basic catalog components on its second call.

Ask: **What's the weather in Paris?**

![The agent replies: I cannot help with that topic. I can only assist with currency-related queries.](https://raw.githubusercontent.com/xbill9/currency-claude-agui-a2ui1/main/docs/a2ui-1-0/img/refusal.png)

No tool runs; the reply is text.

---

#### Step 12 — Every Prompt, Ten Runs, Two Models

`docs/a2ui-1-0/tools/render_suite.py` sends ten prompts ten times each through Next.js. A UI prompt passes when the reply rendered A2UI and no raw `<a2ui` text reached the chat; the weather question passes as text with no UI; the invalid code passes as either.

```shell
python3 docs/a2ui-1-0/tools/render_suite.py 10 gemini-3.8-flash render-suite-gemini-3.8-flash.jsonl
```

```text
# gemini-3.8-flash: 100 of 100 replies rendered clean (10 runs per prompt)
10 of 10: pass | Compare 1 USD in EUR, GBP, JPY and CAD
10 of 10: pass | Compare the euro, pound and Swiss franc against the dollar in a bar chart
10 of 10: pass | Convert 100 USD to XYZ
10 of 10: pass | How much is 250 USD in EUR?
10 of 10: pass | Show a bar chart of 1 USD in EUR, GBP, JPY, CHF and CAD
10 of 10: pass | Show me EUR to USD for the past 6 months and the current rate
10 of 10: pass | Show me the USD to JPY trend over the last 90 days
10 of 10: pass | What's a thousand euros in dollars?
10 of 10: pass | What's the weather in Paris?
10 of 10: pass | Write the A2UI block for a USD to EUR rate card directly in your reply text. Do not call any tool.
```

```text
# gemini-2.5-flash: 100 of 100 replies rendered clean (10 runs per prompt)
```

Every comparison reply on both models came from `RateComparison`, with no call to the rate tool:

```text
## gemini-2.5-flash
10 of 10: no rate-tool call, BarChart=True | Compare 1 USD in EUR, GBP, JPY and CAD
10 of 10: no rate-tool call, BarChart=True | Compare the euro, pound and Swiss franc against the dol
10 of 10: no rate-tool call, BarChart=True | Show a bar chart of 1 USD in EUR, GBP, JPY, CHF and CAD
## gemini-3.8-flash
10 of 10: no rate-tool call, BarChart=True | Compare 1 USD in EUR, GBP, JPY and CAD
10 of 10: no rate-tool call, BarChart=True | Compare the euro, pound and Swiss franc against the dol
10 of 10: no rate-tool call, BarChart=True | Show a bar chart of 1 USD in EUR, GBP, JPY, CHF and CAD
```

The model client makes up to five attempts on a 408, 429 or 5xx answer from the Gemini API, through `Gemini(retry_options=HttpRetryOptions(attempts=5, ...))`, before a user sees an error.

---

#### 🔎 Tip: Headings Come From Markdown in 1.0

Text's `h1`–`h5` variants are gone in 1.0; `caption` and `body` remain, and Text renders Markdown. The macros write `### 250.00 USD = 224.68 EUR` for the headline line, and `@a2ui/react` renders it with `@a2ui/markdown-it`.

---

#### 🔎 Tip: Keep the Macro Catalog on the Model's Side

The macros sit in a separate catalog that exists only in the inference catalogs: `macro_expander.transform_catalogs(BASE_CATALOGS)` adds it for the model and the prompt. The browser's catalogs stay Basic 1.0 plus charts, and the second validation pass confirms every component the browser receives belongs to one of them.

---

#### Compare and Contrast

| Answer | Model writes | Figures from | Rendered, `gemini-3.8-flash` | Rendered, `gemini-2.5-flash` |
| :--- | :--- | :--- | :--- | :--- |
| Rate card 🥇 | `RateCard(...)` | macro, on the server | 20 of 20 | 20 of 20 |
| History chart 🥇 | `RateHistoryChart(...)` | macro, on the server | 20 of 20 | 20 of 20 |
| Comparison 🥇 | `RateComparison(...)` | macro, on the server | 30 of 30 | 30 of 30 |
| Block written as reply text 🥇 | `<a2ui>` text | macro, via the safety net | 10 of 10 | 10 of 10 |
| Last build (0.9) | component JSON | the model, from the MCP result | — | — |

---

#### So, Which One?

For anything the agent shows often, write a macro. The model's output shrinks to one line with the codes and an amount, the figures come from the source on the server, and both validation passes run on what the browser receives. Rate cards, history charts and comparisons all take this path here.

Behind the macros, keep the safety net. It sends A2UI the model writes as reply text through the same tool, so the user sees a card instead of a code block, on both model generations.

For the protocol itself, 1.0 sends a surface in one message, mixes catalogs per component, and opens function calls in both directions, with permissions and composition rules declared in the catalog.

---

#### Summary

The goal of this article was to move a currency agent from A2UI 0.9 to A2UI 1.0 and show what changes for the model, the server and the browser. The key to the solution was server-side macros on the 1.0 protocol, with every UI answer going through one server path: the model names a component and its arguments, and the server fetches the data, builds the components, validates them and sends the surface in one message. The results were:

- 🟢 For a conversion the model wrote one line, `root = RateCard("USD", "EUR", 100)`, and the browser received six Basic 1.0 components with the live rate in one `createSurface`
- 🟢 Ten prompts, ten runs each: 100 of 100 replies rendered clean on `gemini-3.8-flash` and 100 of 100 on `gemini-2.5-flash`
- 🟢 Comparisons came from `RateComparison` in 60 of 60 runs across both models, with no rate-tool call, charted as percent change from a zero line
- 🟢 A2UI written as reply text rendered as UI through the safety net; with the net off it showed as raw text in 5 of 5 runs
- 🟢 One surface mixed two catalogs, each component naming its own `catalogId`
- 🟢 The same Express block compiles to one message on 1.0 and three on 0.9
- 🟢 1.0 adds functions in both directions, function permissions, composition rules, graded validation, `userMessage` on actions, `live` and `hidden`, and `@index`
- ⚠️ Function calls the server writes need `skip_thought_signature_validator` on Gemini 3; `gemini-3.8-flash` rejects them with a 400 otherwise
- ⚠️ 1.0 drops `theme` from `createSurface` and the h1–h5 Text variants

Scope: one laptop running all four services, `gemini-3.8-flash` and `gemini-2.5-flash` at their default settings, ECB reference rates from the Frankfurter API, measured on 2026-11-11 with ten runs per prompt per model. Protocol details come from the 0.9 and 1.0 schemas in `a2ui-core` 0.6.0.

The strategy for moving a generative UI agent to A2UI 1.0 with server-side macros was validated with an incremental step by step approach.

---

#### References

- The repository: https://github.com/xbill9/currency-claude-agui-a2ui1
- Evidence for every figure here: https://github.com/xbill9/currency-claude-agui-a2ui1/tree/main/docs/a2ui-1-0/evidence
- Demo, screenshot and test scripts: https://github.com/xbill9/currency-claude-agui-a2ui1/tree/main/docs/a2ui-1-0/tools
- A2UI v1.0 specification: https://a2ui.org/specification/v1.0-a2ui/
- A2UI: https://a2ui.org
- AG-UI: https://docs.ag-ui.com
- CopilotKit: https://github.com/CopilotKit/CopilotKit
- Google Agent Development Kit: https://github.com/google/adk-python
- Model Context Protocol: https://modelcontextprotocol.io
- Frankfurter API: https://www.frankfurter.dev
- The upstream Currency Agent (A2A + ADK + MCP): https://github.com/jackwotherspoon/currency-agent
