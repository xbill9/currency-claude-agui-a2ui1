"""The safety net that sends A2UI written as reply text through the UI tool."""

from types import SimpleNamespace

from google.adk.models.llm_response import LlmResponse
from google.genai import types

from currency_agent.a2ui_rescue import (
    PAYLOAD_ARG,
    SKIP_SIGNATURE,
    TOOL_NAME,
    rescue_a2ui_text,
)

BLOCK = '<a2ui>\nroot = RateCard("USD", "EUR", 100)\n</a2ui>'


def _response(*parts: types.Part, partial: bool) -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=list(parts)), partial=partial
    )


def _stream(chunks: list[str], invocation: str):
    """Feeds chunks as partials, then the full text as the final response."""
    ctx = SimpleNamespace(invocation_id=invocation)
    shown = []
    for chunk in chunks:
        response = _response(types.Part(text=chunk), partial=True)
        altered = rescue_a2ui_text(ctx, response) or response
        shown.append("".join(p.text or "" for p in altered.content.parts))
    final = _response(types.Part(text="".join(chunks)), partial=False)
    return "".join(shown), rescue_a2ui_text(ctx, final)


def _calls(response: LlmResponse) -> list[types.Part]:
    return [p for p in response.content.parts if p.function_call]


def test_streamed_block_is_held_back_and_becomes_a_tool_call():
    shown, final = _stream(["Here it is. ", "<a2", BLOCK[3:20], BLOCK[20:]], "inv-1")
    assert shown == "Here it is. "
    calls = _calls(final)
    assert len(calls) == 1
    assert calls[0].function_call.name == TOOL_NAME
    assert calls[0].function_call.args == {PAYLOAD_ARG: BLOCK}
    assert calls[0].thought_signature == SKIP_SIGNATURE
    assert [p.text for p in final.content.parts if p.text] == ["Here it is."]


def test_unclosed_block_is_closed():
    _, final = _stream(['<a2ui>\nroot = RateCard("USD", "EUR")'], "inv-2")
    payload = _calls(final)[0].function_call.args[PAYLOAD_ARG]
    assert payload.startswith("<a2ui>") and payload.endswith("</a2ui>")


def test_two_blocks_become_two_calls():
    _, final = _stream([BLOCK, "\n", BLOCK.replace("EUR", "GBP")], "inv-3")
    assert len(_calls(final)) == 2


def test_plain_text_passes_unchanged():
    text = ["The rate is ", "1 < 2 and ", "that is all."]
    shown, final = _stream(text, "inv-4")
    assert shown == "".join(text)
    assert final is None


def test_thought_parts_are_left_alone():
    ctx = SimpleNamespace(invocation_id="inv-5")
    thought = types.Part(text="<a2ui> in a thought", thought=True)
    response = _response(thought, types.Part(text=BLOCK), partial=False)
    final = rescue_a2ui_text(ctx, response)
    assert final.content.parts[0] == thought
    assert len(_calls(final)) == 1


def test_function_call_from_the_model_is_untouched():
    ctx = SimpleNamespace(invocation_id="inv-6")
    call = types.Part(
        function_call=types.FunctionCall(name=TOOL_NAME, args={PAYLOAD_ARG: BLOCK})
    )
    assert rescue_a2ui_text(ctx, _response(call, partial=False)) is None
