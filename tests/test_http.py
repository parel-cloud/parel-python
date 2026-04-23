"""HttpClient + AsyncHttpClient unit tests (retry, timeout, headers)."""

from __future__ import annotations

import httpx
import pytest

from parel_cloud import (
    ParelAuthenticationError,
    ParelConnectionError,
    ParelRateLimitError,
    ParelServerError,
    ParelTimeoutError,
)
from parel_cloud._http import AsyncHttpClient, HttpClient


def _sync_client(handler) -> HttpClient:
    transport = httpx.MockTransport(handler)
    return HttpClient(
        api_key="test-key",
        base_url="https://api.parel.test",
        timeout_s=5.0,
        max_retries=2,
        transport=transport,
    )


def _async_client(handler) -> AsyncHttpClient:
    transport = httpx.MockTransport(handler)
    return AsyncHttpClient(
        api_key="test-key",
        base_url="https://api.parel.test",
        timeout_s=5.0,
        max_retries=2,
        transport=transport,
    )


def test_sync_get_sends_auth_and_user_agent() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update({k.lower(): v for k, v in request.headers.items()})
        return httpx.Response(200, json={"ok": True})

    with _sync_client(handler) as client:
        result = client.request("GET", "/v1/ping")
    assert result == {"ok": True}
    assert seen["authorization"] == "Bearer test-key"
    assert seen["user-agent"].startswith("parel-cloud/0.1.0")
    assert seen["accept"] == "application/json"


def test_sync_post_serializes_json_body() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["content-type"] = request.headers.get("content-type")
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"echo": True})

    with _sync_client(handler) as client:
        result = client.request("POST", "/v1/x", body={"hello": "world"})
    assert result == {"echo": True}
    assert captured["content-type"] == "application/json"
    assert captured["body"] == '{"hello":"world"}' or captured["body"] == '{"hello": "world"}'


def test_sync_get_with_query_omits_none_values() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["query"] = str(request.url.query, "utf-8") if isinstance(request.url.query, bytes) else request.url.query
        return httpx.Response(200, json={})

    with _sync_client(handler) as client:
        client.request(
            "GET",
            "/v1/tasks",
            query={"limit": 10, "status": None, "task_type": "image"},
        )
    q = captured["query"]
    assert "limit=10" in q
    assert "task_type=image" in q
    assert "status=" not in q


def test_sync_auth_error_maps_401() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"error": {"message": "unauthorized", "code": "invalid_api_key"}}
        )

    with _sync_client(handler) as client:
        with pytest.raises(ParelAuthenticationError) as excinfo:
            client.request("GET", "/v1/models")
    assert excinfo.value.status == 401
    assert excinfo.value.code == "invalid_api_key"


def test_sync_retries_on_500_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(500, json={"error": {"message": "boom"}})
        return httpx.Response(200, json={"ok": True})

    with _sync_client(handler) as client:
        result = client.request("GET", "/v1/x")
    assert result == {"ok": True}
    assert calls["n"] == 3


def test_sync_retry_exhausts_and_raises_last_error() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"error": {"message": "still broken"}})

    with _sync_client(handler) as client:
        with pytest.raises(ParelServerError):
            client.request("GET", "/v1/x")
    # max_retries=2 → 1 original + 2 retries = 3 attempts
    assert calls["n"] == 3


def test_sync_post_is_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"error": {"message": "boom"}})

    with _sync_client(handler) as client:
        with pytest.raises(ParelServerError):
            client.request("POST", "/v1/x", body={"k": 1})
    assert calls["n"] == 1


def test_sync_429_triggers_retry_on_get() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                429,
                headers={"retry-after": "0"},
                json={"error": {"message": "slow"}},
            )
        return httpx.Response(200, json={"ok": True})

    with _sync_client(handler) as client:
        result = client.request("GET", "/v1/x")
    assert result == {"ok": True}
    assert calls["n"] == 2


def test_sync_429_non_retried_exposes_retry_after() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"retry-after": "3.5"},
            json={"error": {"message": "slow"}},
        )

    with _sync_client(handler) as client:
        with pytest.raises(ParelRateLimitError) as excinfo:
            client.request("POST", "/v1/x", body={"k": 1})
    assert excinfo.value.retry_after == 3.5


def test_sync_transport_error_maps_to_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    # Disable retries to get a single deterministic error.
    transport = httpx.MockTransport(handler)
    client = HttpClient(
        api_key="k",
        base_url="https://api.parel.test",
        timeout_s=5.0,
        max_retries=0,
        transport=transport,
    )
    with pytest.raises(ParelConnectionError):
        client.request("GET", "/v1/x")
    client.close()


def test_sync_timeout_exception_maps_to_parel_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    transport = httpx.MockTransport(handler)
    client = HttpClient(
        api_key="k",
        base_url="https://api.parel.test",
        timeout_s=5.0,
        max_retries=0,
        transport=transport,
    )
    with pytest.raises(ParelTimeoutError):
        client.request("GET", "/v1/x")
    client.close()


def test_user_agent_suffix_appended() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers.get("user-agent", "")
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    client = HttpClient(
        api_key="k",
        base_url="https://api.parel.test",
        timeout_s=5.0,
        max_retries=0,
        user_agent="my-app/1.0",
        transport=transport,
    )
    client.request("GET", "/v1/x")
    client.close()
    assert seen["ua"].startswith("parel-cloud/")
    assert "my-app/1.0" in seen["ua"]


async def test_async_get_returns_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"async": True})

    async with _async_client(handler) as client:
        result = await client.request("GET", "/v1/ping")
    assert result == {"async": True}


async def test_async_retry_on_500() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(500, json={"error": {"message": "boom"}})
        return httpx.Response(200, json={"ok": True})

    async with _async_client(handler) as client:
        result = await client.request("GET", "/v1/x")
    assert result == {"ok": True}
    assert calls["n"] == 2
