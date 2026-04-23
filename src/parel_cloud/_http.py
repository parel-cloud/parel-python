"""Low-level HTTP client used by every Parel SDK namespace.

Both a synchronous and asynchronous variant are exposed. They share the
retry/backoff/timeout policy and error-decoding logic; only the underlying
:mod:`httpx` transport differs (``httpx.Client`` vs ``httpx.AsyncClient``).

Responsibilities
  * Attach ``Authorization: Bearer <api_key>`` and a spec-compliant
    ``User-Agent`` header.
  * Serialize JSON bodies and decode JSON/text responses.
  * Enforce a per-request timeout.
  * Retry idempotent verbs on 429 / 5xx / transport errors with jittered
    exponential backoff.
  * Translate non-2xx responses into typed :class:`ParelError` subclasses
    via :func:`parse_http_error`.
"""

from __future__ import annotations

import asyncio
import random
import sys
import time
from typing import Any, Mapping, MutableMapping
from urllib.parse import quote as _url_quote

import httpx

from . import __version__ as _PKG_VERSION
from .errors import (
    ParelConnectionError,
    ParelError,
    ParelTimeoutError,
    parse_http_error,
)

# Methods whose effect on the server is (gateway-guaranteed) idempotent and
# therefore safe to retry on transient failures.
IDEMPOTENT_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS", "DELETE", "PUT"})

# Backoff policy (matches the JS SDK): 500ms * 2^attempt capped at 8s, with
# +/-30% jitter.
_BACKOFF_BASE_MS = 500
_BACKOFF_CAP_MS = 8_000


def _default_user_agent() -> str:
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return f"parel-cloud/{_PKG_VERSION} python/{py}"


def _build_query(q: Mapping[str, Any] | None) -> dict[str, str]:
    """httpx accepts a dict of str->str for query; drop ``None`` entries and
    stringify bools the way the gateway expects."""
    if not q:
        return {}
    out: dict[str, str] = {}
    for k, v in q.items():
        if v is None:
            continue
        if isinstance(v, bool):
            out[k] = "true" if v else "false"
        else:
            out[k] = str(v)
    return out


def _backoff_seconds(attempt: int) -> float:
    base = min(_BACKOFF_BASE_MS * (2 ** attempt), _BACKOFF_CAP_MS)
    jitter = base * (0.7 + random.random() * 0.6)
    return jitter / 1000.0


def _is_retryable(err: BaseException) -> bool:
    if isinstance(err, (ParelConnectionError, ParelTimeoutError)):
        return True
    if isinstance(err, ParelError):
        status = err.status
        if status is None:
            return False
        return status == 429 or 500 <= status < 600
    return False


def _decode_body(response: httpx.Response) -> Any:
    if not response.content:
        return None
    ct = response.headers.get("content-type", "")
    text = response.text
    if not text:
        return None
    if "application/json" in ct:
        try:
            return response.json()
        except ValueError:
            return text
    return text


def url_quote(value: str) -> str:
    """Percent-encode a path segment (used by namespaces for IDs)."""
    return _url_quote(value, safe="")


class _BaseHttpClient:
    """Shared configuration between sync and async clients."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_s: float,
        max_retries: int,
        user_agent: str | None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        suffix = f" {user_agent}".rstrip() if user_agent else ""
        self._user_agent = f"{_default_user_agent()}{suffix}"

    def _resolve_retries(self, method: str, override: int | None) -> int:
        if override is not None:
            return override
        return self._max_retries if method.upper() in IDEMPOTENT_METHODS else 0

    def _build_headers(
        self, extra: Mapping[str, str] | None, has_body: bool
    ) -> dict[str, str]:
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": self._user_agent,
            "Accept": "application/json",
        }
        if has_body:
            headers["Content-Type"] = "application/json"
        if extra:
            for k, v in extra.items():
                headers[k] = v
        return headers

    def _httpx_timeout(self, per_request: float | None) -> httpx.Timeout:
        effective = per_request if per_request is not None else self._timeout_s
        if effective <= 0:
            return httpx.Timeout(None)
        return httpx.Timeout(
            connect=min(10.0, effective),
            read=effective,
            write=max(30.0, effective),
            pool=5.0,
        )

    def _raise_if_error(self, response: httpx.Response) -> Any:
        if response.is_success:
            return _decode_body(response)
        body = _decode_body(response)
        raise parse_http_error(response.status_code, body, response.headers)


class HttpClient(_BaseHttpClient):
    """Synchronous HTTP client."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_s: float,
        max_retries: int,
        user_agent: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout_s=timeout_s,
            max_retries=max_retries,
            user_agent=user_agent,
        )
        self._client = httpx.Client(
            base_url=self._base_url,
            transport=transport,
            timeout=self._httpx_timeout(timeout_s),
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        query: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout_s: float | None = None,
        max_retries: int | None = None,
    ) -> Any:
        retries = self._resolve_retries(method, max_retries)
        last: BaseException | None = None
        for attempt in range(retries + 1):
            try:
                return self._dispatch(
                    method=method,
                    path=path,
                    body=body,
                    query=query,
                    headers=headers,
                    timeout_s=timeout_s,
                )
            except BaseException as err:  # noqa: BLE001 — retried or re-raised below
                last = err
                if attempt >= retries or not _is_retryable(err):
                    raise
                time.sleep(_backoff_seconds(attempt))
        assert last is not None  # pragma: no cover — unreachable
        raise last

    def _dispatch(
        self,
        *,
        method: str,
        path: str,
        body: Any,
        query: Mapping[str, Any] | None,
        headers: Mapping[str, str] | None,
        timeout_s: float | None,
    ) -> Any:
        try:
            response = self._client.request(
                method.upper(),
                path,
                params=_build_query(query) or None,
                json=body if body is not None else None,
                headers=self._build_headers(headers, has_body=body is not None),
                timeout=self._httpx_timeout(timeout_s),
            )
        except httpx.TimeoutException as err:
            raise ParelTimeoutError(f"Request timed out: {err}") from err
        except httpx.TransportError as err:
            raise ParelConnectionError(str(err) or "Network error", cause=err) from err
        return self._raise_if_error(response)


class AsyncHttpClient(_BaseHttpClient):
    """Asynchronous HTTP client backed by :class:`httpx.AsyncClient`."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_s: float,
        max_retries: int,
        user_agent: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout_s=timeout_s,
            max_retries=max_retries,
            user_agent=user_agent,
        )
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            transport=transport,
            timeout=self._httpx_timeout(timeout_s),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsyncHttpClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        query: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout_s: float | None = None,
        max_retries: int | None = None,
    ) -> Any:
        retries = self._resolve_retries(method, max_retries)
        last: BaseException | None = None
        for attempt in range(retries + 1):
            try:
                return await self._dispatch(
                    method=method,
                    path=path,
                    body=body,
                    query=query,
                    headers=headers,
                    timeout_s=timeout_s,
                )
            except BaseException as err:  # noqa: BLE001
                last = err
                if attempt >= retries or not _is_retryable(err):
                    raise
                await asyncio.sleep(_backoff_seconds(attempt))
        assert last is not None
        raise last

    async def _dispatch(
        self,
        *,
        method: str,
        path: str,
        body: Any,
        query: Mapping[str, Any] | None,
        headers: Mapping[str, str] | None,
        timeout_s: float | None,
    ) -> Any:
        try:
            response = await self._client.request(
                method.upper(),
                path,
                params=_build_query(query) or None,
                json=body if body is not None else None,
                headers=self._build_headers(headers, has_body=body is not None),
                timeout=self._httpx_timeout(timeout_s),
            )
        except httpx.TimeoutException as err:
            raise ParelTimeoutError(f"Request timed out: {err}") from err
        except httpx.TransportError as err:
            raise ParelConnectionError(str(err) or "Network error", cause=err) from err
        return self._raise_if_error(response)


__all__ = ["HttpClient", "AsyncHttpClient", "IDEMPOTENT_METHODS", "url_quote"]
