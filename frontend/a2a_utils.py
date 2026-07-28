# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging

from a2a.utils.constants import (
    AGENT_CARD_WELL_KNOWN_PATH,
    EXTENDED_AGENT_CARD_PATH,
    PREV_AGENT_CARD_WELL_KNOWN_PATH,
)

# Import the consolidated client factory
from starlette.datastructures import URL
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

logger = logging.getLogger(__name__)


async def a2a_card_dispatch(
    request: StarletteRequest, call_next: RequestResponseEndpoint
) -> Response:
    """Handles requests for A2A Agent Cards.

    Ensures that the agent's internal URL matches the public-facing URL (protocol,
    hostname, and port) from the request headers. This is critical for agents
    behind proxies like Cloud Run or Load Balancers.
    """
    response = await call_next(request)

    path = request.url.path
    is_agent_card_request = response.status_code == 200 and (
        path.endswith(AGENT_CARD_WELL_KNOWN_PATH)
        or path.endswith(PREV_AGENT_CARD_WELL_KNOWN_PATH)
        or path.endswith(EXTENDED_AGENT_CARD_PATH)
    )

    if not is_agent_card_request:
        return response

    # Extract and modify the card body
    try:
        body = await _get_response_body(response)
        card = json.loads(body)

        # Use request headers (x-forwarded-*) to determine the public URL
        headers = request.headers
        host = headers.get("x-forwarded-host", request.url.hostname)
        scheme = headers.get("x-forwarded-proto", request.url.scheme or "http").lower()
        port = headers.get("x-forwarded-port", request.url.port)

        # Strip default ports for cleaner URLs
        if port and (
            (scheme == "http" and port == "80") or (scheme == "https" and port == "443")
        ):
            port = None

        agent_url = URL(card["url"]).replace(
            scheme=scheme,
            hostname=host,
            port=port,
        )
        card["url"] = str(agent_url)

        # Reconstruct the response
        response_headers = dict(response.headers)
        response_headers.pop("content-length", None)  # Let Starlette recalculate

        return Response(
            json.dumps(card).encode(response.charset or "utf-8"),
            media_type="application/json",
            headers=response_headers,
        )
    except Exception as e:
        logger.error(f"Failed to rewrite A2A agent card: {e}")
        return response


async def _get_response_body(response: Response) -> str:
    """Helper to safely extract the response body from various Starlette response types."""
    if hasattr(response, "body"):
        body = response.body
    elif hasattr(response, "body_iterator"):
        body = b""
        async for chunk in response.body_iterator:  # type: ignore
            if isinstance(chunk, str):
                chunk = chunk.encode(response.charset or "utf-8")
            body += chunk
    else:
        return ""

    if isinstance(body, memoryview):
        body = body.tobytes()

    return body.decode(response.charset or "utf-8")
