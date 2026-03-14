"""Tests for Audio Transcription API."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from main import app, settings, truncate_transcript
from providers.ollama import (
    OllamaTranscriptionResult,
    OllamaProviderTimeout,
    OllamaProviderError,
    OllamaProviderBadResponse,
    OllamaWhisperProvider,
)


API_KEY = "changeme"
HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/octet-stream",
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# --- truncate_transcript ---


def test_truncate_short_text():
    assert truncate_transcript("hello world") == "hello world"


def test_truncate_exact_limit():
    text = " ".join(f"w{i}" for i in range(10))
    assert truncate_transcript(text) == text


def test_truncate_long_text():
    text = " ".join(f"word{i}" for i in range(20))
    result = truncate_transcript(text)
    assert len(result.split()) == 10


def test_truncate_custom_limit():
    assert truncate_transcript("a b c d e f", max_words=3) == "a b c"


def test_truncate_whitespace():
    assert truncate_transcript("  hello   world  ") == "hello world"


# --- Health endpoint ---


def test_health_ok(client):
    with patch.object(
        app.state.ollama_provider, "healthcheck", new_callable=AsyncMock, return_value=True
    ):
        resp = client.get("/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_health_ollama_timeout(client):
    with patch.object(
        app.state.ollama_provider,
        "healthcheck",
        new_callable=AsyncMock,
        side_effect=OllamaProviderTimeout("timeout"),
    ):
        resp = client.get("/v1/health")
        assert resp.status_code == 504


def test_health_ollama_error(client):
    with patch.object(
        app.state.ollama_provider,
        "healthcheck",
        new_callable=AsyncMock,
        side_effect=OllamaProviderError("fail"),
    ):
        resp = client.get("/v1/health")
        assert resp.status_code == 502


# --- Auth ---


def test_missing_api_key(client):
    resp = client.post(
        "/v1/transcriptions",
        content=b"audio",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_wrong_api_key(client):
    resp = client.post(
        "/v1/transcriptions",
        content=b"audio",
        headers={"X-API-Key": "wrong", "Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 401


# --- Content-Type validation ---


def test_wrong_content_type(client):
    resp = client.post(
        "/v1/transcriptions",
        content=b"audio",
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
    )
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "unsupported_media_type"


# --- Empty body ---


def test_empty_body(client):
    resp = client.post(
        "/v1/transcriptions",
        content=b"",
        headers=HEADERS,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_request"


# --- Payload too large ---


def test_payload_too_large_via_content_length(client):
    max_bytes = settings.max_audio_size_mb * 1024 * 1024
    resp = client.post(
        "/v1/transcriptions",
        content=b"x",
        headers={**HEADERS, "Content-Length": str(max_bytes + 1)},
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "payload_too_large"


# --- Successful transcription ---


def test_transcription_success(client):
    mock_result = OllamaTranscriptionResult(
        text="schalte bitte das licht im wohnzimmer an und mache es hell",
        language="de",
        duration=2.5,
    )
    with patch.object(
        app.state.ollama_provider,
        "transcribe",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = client.post(
            "/v1/transcriptions",
            content=b"\x00\x01\x02\x03",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["language"] == "de"
        assert data["duration"] == 2.5
        assert "request_id" in data
        # Text should be truncated to 10 words
        assert len(data["text"].split()) <= 10


# --- Ollama errors during transcription ---


def test_transcription_ollama_timeout(client):
    with patch.object(
        app.state.ollama_provider,
        "transcribe",
        new_callable=AsyncMock,
        side_effect=OllamaProviderTimeout("timeout"),
    ):
        resp = client.post(
            "/v1/transcriptions",
            content=b"\x00\x01\x02",
            headers=HEADERS,
        )
        assert resp.status_code == 504
        assert resp.json()["error"]["code"] == "gateway_timeout"


def test_transcription_ollama_bad_response(client):
    with patch.object(
        app.state.ollama_provider,
        "transcribe",
        new_callable=AsyncMock,
        side_effect=OllamaProviderBadResponse("bad"),
    ):
        resp = client.post(
            "/v1/transcriptions",
            content=b"\x00\x01\x02",
            headers=HEADERS,
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_request"


def test_transcription_ollama_upstream_error(client):
    with patch.object(
        app.state.ollama_provider,
        "transcribe",
        new_callable=AsyncMock,
        side_effect=OllamaProviderError("upstream fail"),
    ):
        resp = client.post(
            "/v1/transcriptions",
            content=b"\x00\x01\x02",
            headers=HEADERS,
        )
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "bad_gateway"


# --- Request ID ---


def test_request_id_in_response(client):
    mock_result = OllamaTranscriptionResult(text="hello", language="en", duration=1.0)
    with patch.object(
        app.state.ollama_provider,
        "transcribe",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = client.post(
            "/v1/transcriptions",
            content=b"\x00\x01\x02",
            headers=HEADERS,
        )
        assert "X-Request-ID" in resp.headers
        assert resp.json()["request_id"] == resp.headers["X-Request-ID"]


def test_custom_request_id(client):
    mock_result = OllamaTranscriptionResult(text="hello", language="en", duration=1.0)
    with patch.object(
        app.state.ollama_provider,
        "transcribe",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = client.post(
            "/v1/transcriptions",
            content=b"\x00\x01\x02",
            headers={**HEADERS, "X-Request-ID": "my-custom-id"},
        )
        assert resp.headers["X-Request-ID"] == "my-custom-id"
        assert resp.json()["request_id"] == "my-custom-id"


# --- Multiple API keys ---


def test_multiple_api_keys(client):
    original = settings.api_keys
    settings.api_keys = "key1,key2,key3"
    mock_result = OllamaTranscriptionResult(text="hello", language="en", duration=1.0)
    try:
        with patch.object(
            app.state.ollama_provider,
            "transcribe",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.post(
                "/v1/transcriptions",
                content=b"\x00\x01\x02",
                headers={
                    "X-API-Key": "key2",
                    "Content-Type": "application/octet-stream",
                },
            )
            assert resp.status_code == 200
    finally:
        settings.api_keys = original
