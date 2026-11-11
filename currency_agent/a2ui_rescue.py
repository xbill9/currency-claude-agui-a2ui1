"""Turns an A2UI block that the model writes as reply text into the UI tool call.

The model is told to pass A2UI to the ``send_a2ui_json_to_client`` tool. When it
writes the ``<a2ui>`` block into its reply instead, this ``after_model_callback``

* holds back streamed text from the point ``<a2ui`` starts, so the raw block
  never reaches the chat, and
* rewrites the final response so that each block becomes a call to the tool,
  which compiles, expands and validates it like any other A2UI.

ADK runs ``after_model_callback`` on every streamed chunk and on the final
response, and executes the function calls in the final response.
"""

from __future__ import annotations

import logging
import re

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.genai import types

TOOL_NAME = "send_a2ui_json_to_client"
PAYLOAD_ARG = "a2ui_payload"
MARKER = "<a2ui"
CLOSE = "</a2ui>"
# Gemini 3 rejects a function call in the current turn that has no thought
# signature (400 INVALID_ARGUMENT); this value marks a call the server wrote.
SKIP_SIGNATURE = b"skip_thought_signature_validator"

logger = logging.getLogger(__name__)

_BLOCK = re.compile(r"<a2ui>.*?(?:</a2ui>|\Z)", re.DOTALL)
# Streamed text per invocation: everything received, and how much was let through.
_streams: dict[str, dict[str, object]] = {}


def _is_text(part: types.Part) -> bool:
    return part.text is not None and not part.thought


def _held_back(text: str) -> int:
    """Length of the tail of ``text`` that could be the start of ``<a2ui``."""
    for n in range(min(len(MARKER) - 1, len(text)), 0, -1):
        if MARKER.startswith(text[-n:]):
            return n
    return 0


def _with_parts(response: LlmResponse, parts: list[types.Part]) -> LlmResponse:
    role = response.content.role if response.content else "model"
    return response.model_copy(
        update={"content": types.Content(role=role or "model", parts=parts)}
    )


def _filter_partial(key: str, response: LlmResponse) -> LlmResponse | None:
    parts = response.content.parts or []
    chunk = "".join(p.text for p in parts if _is_text(p))
    if not chunk:
        return None
    state = _streams.setdefault(key, {"text": "", "sent": 0})
    state["text"] = text = str(state["text"]) + chunk
    sent = int(state["sent"])
    start = text.find(MARKER)
    end = start if start >= 0 else len(text) - _held_back(text)
    release = text[sent:end] if end > sent else ""
    state["sent"] = max(sent, end)
    if release == chunk:
        return None
    others = [p for p in parts if not _is_text(p)]
    return _with_parts(
        response, others + ([types.Part(text=release)] if release else [])
    )


def _rewrite_final(response: LlmResponse) -> LlmResponse | None:
    parts = response.content.parts or []
    text = "".join(p.text for p in parts if _is_text(p))
    blocks = _BLOCK.findall(text)
    if not blocks:
        return None
    rest = _BLOCK.sub("", text).strip()
    new_parts = [p for p in parts if not _is_text(p)]
    if rest:
        new_parts.append(types.Part(text=rest))
    for block in blocks:
        payload = (
            block if block.rstrip().endswith(CLOSE) else block.rstrip() + "\n" + CLOSE
        )
        new_parts.append(
            types.Part(
                function_call=types.FunctionCall(
                    name=TOOL_NAME, args={PAYLOAD_ARG: payload}
                ),
                thought_signature=SKIP_SIGNATURE,
            )
        )
    logger.info(
        "A2UI written as reply text: sent %d block(s) through %s",
        len(blocks),
        TOOL_NAME,
    )
    return _with_parts(response, new_parts)


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
