# Copyright 2026 Google LLC
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

import logging
import subprocess
from urllib.parse import urlparse

# Monkeypatch to fix ImportError: cannot import name 'GEN_AI_INPUT_MESSAGES' from 'opentelemetry'
try:
    import opentelemetry.semconv._incubating.attributes.gen_ai_attributes as gen_ai_attr

    if not hasattr(gen_ai_attr, "GEN_AI_INPUT_MESSAGES"):
        setattr(gen_ai_attr, "GEN_AI_INPUT_MESSAGES", "gen_ai.input.messages")
    if not hasattr(gen_ai_attr, "GEN_AI_OUTPUT_MESSAGES"):
        setattr(gen_ai_attr, "GEN_AI_OUTPUT_MESSAGES", "gen_ai.output.messages")
    if not hasattr(gen_ai_attr, "GEN_AI_RESPONSE_FINISH_REASONS"):
        setattr(
            gen_ai_attr,
            "GEN_AI_RESPONSE_FINISH_REASONS",
            "gen_ai.response.finish_reasons",
        )
    if not hasattr(gen_ai_attr, "GEN_AI_SYSTEM_INSTRUCTIONS"):
        setattr(gen_ai_attr, "GEN_AI_SYSTEM_INSTRUCTIONS", "gen_ai.system.instructions")
    if not hasattr(gen_ai_attr, "GEN_AI_USAGE_INPUT_TOKENS"):
        setattr(gen_ai_attr, "GEN_AI_USAGE_INPUT_TOKENS", "gen_ai.usage.input_tokens")
    if not hasattr(gen_ai_attr, "GEN_AI_USAGE_OUTPUT_TOKENS"):
        setattr(gen_ai_attr, "GEN_AI_USAGE_OUTPUT_TOKENS", "gen_ai.usage.output_tokens")
except ImportError:
    pass

# Monkeypatch to fix ImportError: cannot import name 'SamplingCapability' from 'mcp'
try:
    import mcp
    import mcp.types

    if not hasattr(mcp, "SamplingCapability"):
        setattr(mcp, "SamplingCapability", mcp.types.SamplingCapability)
except ImportError:
    pass

import httpx
from google.adk.agents.remote_a2a_agent import DEFAULT_TIMEOUT
from google.auth.exceptions import DefaultCredentialsError
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google.oauth2.id_token import fetch_id_token_credentials

logger = logging.getLogger(__name__)


class _IdentityTokenAuth(httpx.Auth):
    """Internal helper for Google identity token authentication."""

    requires_request_body = False

    def __init__(self, remote_service_url: str):
        parsed_url = urlparse(remote_service_url)
        self.root_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        self.session = None

    def auth_flow(self, request):
        id_token = None

        # 1. Try to use existing session token
        if self.session and self.session.credentials:
            id_token = self.session.credentials.token

        # 2. If no token, attempt to fetch from Cloud Metadata or Local gcloud
        if not id_token:
            try:
                # Attempt Cloud Metadata fetch (works on Cloud Run/GCE)
                credentials = fetch_id_token_credentials(audience=self.root_url)
                credentials.refresh(Request())
                self.session = AuthorizedSession(credentials)
                id_token = self.session.credentials.token
            except (DefaultCredentialsError, Exception) as e:
                logger.debug(f"Cloud credentials not found, falling back to local: {e}")

            if not id_token:
                # Local development fallback: use gcloud CLI
                id_token = self._get_local_identity_token()

        if id_token:
            request.headers["Authorization"] = f"Bearer {id_token}"
        else:
            logger.warning(f"Failed to obtain identity token for {self.root_url}")

        yield request

    def _get_local_identity_token(self) -> str | None:
        """Fetches identity token from gcloud CLI for local development."""
        try:
            # Use -q to avoid interactive prompts
            token = (
                subprocess.check_output(
                    ["gcloud", "auth", "print-identity-token", "-q"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )

            if token:
                # Also try to fetch refresh token to populate session for consistency
                try:
                    refresh_token = (
                        subprocess.check_output(
                            ["gcloud", "auth", "print-refresh-token", "-q"],
                            stderr=subprocess.DEVNULL,
                        )
                        .decode()
                        .strip()
                    )
                    self.session = AuthorizedSession(
                        Credentials(
                            token=token, id_token=token, refresh_token=refresh_token
                        )
                    )
                except subprocess.SubprocessError:
                    pass
                return token
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.error(
                "gcloud CLI not found or not authenticated. Run 'gcloud auth login'."
            )
        return None


def create_authenticated_client(
    remote_service_url: str, timeout: float = DEFAULT_TIMEOUT
) -> httpx.AsyncClient:
    """Creates an httpx.AsyncClient with Google identity token authentication.

    Identity tokens are automatically sourced from the environment:
      - In GCP (Cloud Run, GKE, etc.): Uses the Service Account's metadata server.
      - Locally: Uses 'gcloud auth print-identity-token'.

    Args:
        remote_service_url: URL of the target service.
        timeout: Request timeout (defaults to ADK DEFAULT_TIMEOUT).

    Returns:
        An authenticated httpx.AsyncClient.
    """
    if "localhost" in remote_service_url or "127.0.0.1" in remote_service_url:
        logger.info(f"Bypassing authentication for local URL: {remote_service_url}")
        return httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
        )

    return httpx.AsyncClient(
        auth=_IdentityTokenAuth(remote_service_url),
        follow_redirects=True,
        timeout=timeout,
    )
