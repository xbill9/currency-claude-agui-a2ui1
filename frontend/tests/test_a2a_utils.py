import json

import pytest
from a2a_utils import a2a_card_dispatch
from starlette.requests import Request
from starlette.responses import Response


@pytest.mark.asyncio
async def test_a2a_card_dispatch_rewrites_url():
    # Mock agent card
    card = {"name": "test-agent", "url": "http://localhost:8080"}

    async def call_next(request):
        return Response(
            content=json.dumps(card), status_code=200, media_type="application/json"
        )

    # Mock request with x-forwarded headers (Cloud Run style)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/a2a/agent/.well-known/agent-card.json",
        "headers": [
            (b"x-forwarded-host", b"public-agent.a.run.app"),
            (b"x-forwarded-proto", b"https"),
            (b"x-forwarded-port", b"443"),
        ],
    }
    request = Request(scope)

    response = await a2a_card_dispatch(request, call_next)

    assert response.status_code == 200
    body = json.loads(response.body)
    assert body["url"] == "https://public-agent.a.run.app"


@pytest.mark.asyncio
async def test_a2a_card_dispatch_ignores_non_card_requests():
    async def call_next(request):
        return Response(content="some data", status_code=200)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/some-endpoint",
        "headers": [],
    }
    request = Request(scope)

    response = await a2a_card_dispatch(request, call_next)
    assert response.body == b"some data"
