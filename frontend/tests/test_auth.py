from unittest.mock import MagicMock, patch

import httpx
from authenticated_httpx import _IdentityTokenAuth, create_authenticated_client


def test_create_authenticated_client_localhost():
    client = create_authenticated_client("http://localhost:8080")
    assert isinstance(client, httpx.AsyncClient)
    # Check that it doesn't have our custom auth
    assert not isinstance(client._auth, _IdentityTokenAuth)


@patch("authenticated_httpx.fetch_id_token_credentials")
def test_identity_token_auth_cloud_metadata(mock_fetch):
    mock_creds = MagicMock()
    mock_creds.token = "fake-cloud-token"
    mock_fetch.return_value = mock_creds

    auth = _IdentityTokenAuth("https://some-service.a.run.app")
    request = httpx.Request("GET", "https://some-service.a.run.app/api")

    # Trigger the auth flow
    generator = auth.auth_flow(request)
    authed_request = next(generator)

    assert authed_request.headers["Authorization"] == "Bearer fake-cloud-token"
    mock_fetch.assert_called_once_with(audience="https://some-service.a.run.app")


@patch("authenticated_httpx.fetch_id_token_credentials")
@patch("authenticated_httpx.subprocess.check_output")
def test_identity_token_auth_local_fallback(mock_subprocess, mock_fetch):
    # Simulate Cloud Metadata failing
    mock_fetch.side_effect = Exception("Not in cloud")

    # Simulate gcloud succeeding
    mock_subprocess.return_value = b"fake-local-token\n"

    auth = _IdentityTokenAuth("https://some-service.a.run.app")
    request = httpx.Request("GET", "https://some-service.a.run.app/api")

    generator = auth.auth_flow(request)
    authed_request = next(generator)

    import subprocess

    assert authed_request.headers["Authorization"] == "Bearer fake-local-token"
    mock_subprocess.assert_any_call(
        ["gcloud", "auth", "print-identity-token", "-q"], stderr=subprocess.DEVNULL
    )
