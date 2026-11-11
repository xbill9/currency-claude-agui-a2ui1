---
name: add-a2ui-macro
description: How to add or change an A2UI 1.0 server-side macro (like RateCard, RateHistoryChart) or a custom catalog component in the currency agent, keeping the Python catalog, the macro expander and the React renderer in sync. Use when adding a new UI card/chart the agent can emit, or changing chart component props.
---

Macros are Python functions the model calls by name inside its A2UI Express payload, e.g. `RateCard("USD", "EUR", 250)`. `MacroExpander` (in `currency_agent/agent.py`) runs them on the server and replaces them with plain Basic-catalog and charts-catalog components. The model never sees the data they fetch.

## Adding a macro (`currency_agent/macros.py`)

1. Write a function decorated with `@macro` that returns a builder node from `a2ui.builder.v1_0` (`Card`, `Column`, `Text`, `Divider`, ...) or a chart builder (`LineChart`, `BarChart`).
2. The **docstring and type hints are the model's API**: the expander turns them into the macro's catalog entry. Describe each arg in an `Args:` section and say which figures the server looks up so the model doesn't pass them.
3. **Arguments are untrusted model output.** Validate currency codes with `_code()`, clamp numbers (as `RateHistoryChart` clamps `days` to 7–365), and fetch data with `_get()` (Frankfurter, `FRANKFURTER_URL`, 10 s timeout). Raise on bad input; the expander runs with `on_error="raise"`.
4. Append it to `MACROS` at the bottom of the file.
5. Mention it in `ROLE_INSTRUCTION` in `agent.py` so the model knows when to prefer it.

## Adding or changing a custom component (chart etc.)

A macro may only expand to components in `BASE_CATALOGS` (Basic 1.0 + charts). A new component must be added in **three places, identically**:

1. `currency_agent/custom_catalog.json`: add the schema under `components` and a `$ref` in `$defs.anyComponent.oneOf`. Keep `catalogId` and `"protocolVersion": "1.0"`.
2. `currency_agent/macros.py`: a `ComponentBuilderNode` subclass with `component: Literal["Name"]` and matching fields.
3. `frontend-react/src/components/A2UICustomCatalog.tsx`: a zod schema plus `createComponentImplementation`, added to `chartsCatalog`. `CHARTS_CATALOG_ID` must equal the JSON `catalogId`.

If the legacy `frontend/` renders the payload, check it handles the new component too.

## Check it

- Unit-level: in `python3`, import `currency_agent.agent`, call the macro directly, and pass the expanded output through `validate_payload(BASE_CATALOGS, wire)` the way `_parse_payload` does.
- End to end: `/verify-stack`, then ask the UI for something that should trigger the macro and confirm it renders.
