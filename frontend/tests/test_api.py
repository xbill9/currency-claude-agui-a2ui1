import os
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch.dict(os.environ, {"AGENT_SERVER_URL": "http://fake-server"})
@patch("main.get_a2a_client", new_callable=AsyncMock)
def test_chat_stream_missing_config(mock_get_a2a, client):
    # Temporarily remove AGENT_SERVER_URL from env for this test
    with patch.dict(os.environ, {}, clear=True):
        import main

        main.agent_server_url = None
        response = client.post(
            "/api/chat_stream", json={"message": "test", "user_id": "user1"}
        )
        assert response.status_code == 200
        assert "error" in response.json()
        assert (
            "AGENT_SERVER_URL environment variable not set" in response.json()["error"]
        )


@patch.dict(os.environ, {"AGENT_SERVER_URL": "http://fake-server"})
@patch("main.get_a2a_client", new_callable=AsyncMock)
def test_chat_stream_success(mock_get_a2a_client, client):
    import main

    main.agent_server_url = "http://fake-server"

    # Mock A2AClient and send_message_streaming
    mock_a2a_client = MagicMock()
    mock_get_a2a_client.return_value = mock_a2a_client

    # Mock the send_message_streaming generator
    async def mock_streaming_responses(*args, **kwargs):
        from a2a.types import (
            SendStreamingMessageResponse,
            SendStreamingMessageSuccessResponse,
            Message,
            Part,
            TextPart,
            Role,
            TaskStatusUpdateEvent,
            TaskStatus,
            TaskState,
        )

        status_event = TaskStatusUpdateEvent(
            context_id="session1",
            final=False,
            kind="status-update",
            task_id="task1",
            status=TaskStatus(state=TaskState.working),
        )
        yield SendStreamingMessageResponse(
            root=SendStreamingMessageSuccessResponse(
                id="req1", jsonrpc="2.0", result=status_event
            )
        )

        msg = Message(
            role=Role.agent,
            message_id="msg1",
            parts=[Part(TextPart(kind="text", text="Researching..."))],
            context_id="session1",
        )
        yield SendStreamingMessageResponse(
            root=SendStreamingMessageSuccessResponse(
                id="req2", jsonrpc="2.0", result=msg
            )
        )

        msg2 = Message(
            role=Role.agent,
            message_id="msg2",
            parts=[Part(TextPart(kind="text", text="Course content."))],
            context_id="session1",
        )
        yield SendStreamingMessageResponse(
            root=SendStreamingMessageSuccessResponse(
                id="req3", jsonrpc="2.0", result=msg2
            )
        )

    mock_a2a_client.send_message_streaming.side_effect = mock_streaming_responses

    response = client.post(
        "/api/chat_stream", json={"message": "test", "user_id": "user1"}
    )
    assert response.status_code == 200

    # Check if the response is an NDJSON stream
    lines = response.text.strip().split("\n")
    assert len(lines) > 0

    import json

    data = [json.loads(line) for line in lines]

    # Check for progress and result types
    types = [d["type"] for d in data]
    assert "progress" in types
    assert "result" in types

    # Find result
    result = next(d for d in data if d["type"] == "result")
    assert result["text"] == "Researching...Course content."
