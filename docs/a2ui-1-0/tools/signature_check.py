"""Does a server-written function call in the current turn need a thought signature?

usage: GOOGLE_API_KEY=... python3 signature_check.py MODEL [MODEL ...]
"""

import sys

from google import genai
from google.genai import types

client = genai.Client()
tool = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="send_a2ui_json_to_client",
            description="Send A2UI",
            parameters=types.Schema(
                type="OBJECT",
                properties={"a2ui_payload": types.Schema(type="STRING")},
                required=["a2ui_payload"],
            ),
        )
    ]
)


def history(signature: bytes | None) -> list[types.Content]:
    call = types.Part(
        function_call=types.FunctionCall(
            name="send_a2ui_json_to_client",
            args={"a2ui_payload": '<a2ui>\nroot = RateCard("USD", "EUR")\n</a2ui>'},
        ),
        thought_signature=signature,
    )
    result = types.Part(
        function_response=types.FunctionResponse(
            name="send_a2ui_json_to_client", response={"ok": True}
        )
    )
    return [
        types.Content(role="user", parts=[types.Part(text="Show USD to EUR")]),
        types.Content(role="model", parts=[call]),
        types.Content(role="user", parts=[result]),
    ]


for model in sys.argv[1:]:
    for label, sig in (
        ("no signature", None),
        ("skip_thought_signature_validator", b"skip_thought_signature_validator"),
    ):
        try:
            client.models.generate_content(
                model=model,
                contents=history(sig),
                config=types.GenerateContentConfig(tools=[tool]),
            )
            print(f"{model:18} {label:34} accepted")
        except Exception as e:  # noqa: BLE001 - print the API's answer
            print(f"{model:18} {label:34} rejected: {str(e)[:110]}")
