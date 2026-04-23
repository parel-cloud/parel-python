"""``parel.compare`` — multi-model head-to-head runs + conversations.

Wraps ``/v1/compare/*``. The :meth:`run` convenience submits a quick run and
polls until terminal; lower-level ``*_run`` / ``*_dataset`` /
``*_conversation`` methods expose the full surface.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Mapping

from .._http import AsyncHttpClient, HttpClient, url_quote
from .._polling import apoll_until_terminal, poll_until_terminal
from ..types import CompareRun

_COMPARE_TERMINAL: frozenset[str] = frozenset({"completed", "failed", "cancelled"})


def _unwrap_list(payload: Any, key: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, Mapping) and isinstance(payload.get(key), list):
        return payload[key]
    return []


def _is_compare_terminal(run: CompareRun) -> bool:
    return str(run.get("status", "")) in _COMPARE_TERMINAL


class CompareNamespace:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    # ---------------------- runs ----------------------

    def run(
        self,
        *,
        models: list[str],
        prompt: str | None = None,
        dataset_id: str | None = None,
        conversation_id: str | None = None,
        name: str | None = None,
        wait: bool = True,
        timeout_s: float = 600.0,
        interval_s: float = 3.0,
        cancel_event: threading.Event | None = None,
        **extra: Any,
    ) -> CompareRun:
        body: dict[str, Any] = {"models": models, **extra}
        if prompt is not None:
            body["prompt"] = prompt
        if dataset_id is not None:
            body["dataset_id"] = dataset_id
        if conversation_id is not None:
            body["conversation_id"] = conversation_id
        if name is not None:
            body["name"] = name

        submitted = self._http.request("POST", "/v1/compare/runs", body=body)
        if not wait:
            return submitted
        run_id = submitted["id"]
        return poll_until_terminal(
            lambda: self.get_run(run_id),
            _is_compare_terminal,
            timeout_s=timeout_s,
            interval_s=interval_s,
            cancel_event=cancel_event,
        )

    def list_runs(
        self,
        *,
        limit: int | None = None,
        status: str | None = None,
    ) -> list[CompareRun]:
        res = self._http.request(
            "GET", "/v1/compare/runs", query={"limit": limit, "status": status}
        )
        return _unwrap_list(res, "runs")

    def get_run(self, run_id: str) -> CompareRun:
        return self._http.request("GET", f"/v1/compare/runs/{url_quote(run_id)}")

    def cancel_run(self, run_id: str) -> CompareRun:
        return self._http.request(
            "POST", f"/v1/compare/runs/{url_quote(run_id)}/cancel"
        )

    def save_run(self, run_id: str) -> dict[str, Any]:
        return self._http.request(
            "POST", f"/v1/compare/runs/{url_quote(run_id)}/save"
        )

    def mark_winner(self, run_id: str, lane_id: str) -> dict[str, Any]:
        return self._http.request(
            "POST",
            f"/v1/compare/runs/{url_quote(run_id)}/lanes/{url_quote(lane_id)}/winner",
        )

    # ---------------------- datasets ----------------------

    def create_dataset(
        self,
        *,
        name: str,
        test_cases: list[Mapping[str, Any]],
        **extra: Any,
    ) -> dict[str, Any]:
        return self._http.request(
            "POST",
            "/v1/compare/datasets",
            body={"name": name, "test_cases": list(test_cases), **extra},
        )

    def list_datasets(self) -> list[dict[str, Any]]:
        res = self._http.request("GET", "/v1/compare/datasets")
        return _unwrap_list(res, "datasets")

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        return self._http.request(
            "GET", f"/v1/compare/datasets/{url_quote(dataset_id)}"
        )

    # ---------------------- conversations ----------------------

    def create_conversation(self, **params: Any) -> dict[str, Any]:
        return self._http.request("POST", "/v1/compare/conversations", body=params)

    def list_conversations(self) -> list[dict[str, Any]]:
        res = self._http.request("GET", "/v1/compare/conversations")
        return _unwrap_list(res, "conversations")

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        return self._http.request(
            "GET", f"/v1/compare/conversations/{url_quote(conversation_id)}"
        )

    def add_turn(self, conversation_id: str, **body: Any) -> dict[str, Any]:
        return self._http.request(
            "POST",
            f"/v1/compare/conversations/{url_quote(conversation_id)}/turns",
            body=body,
        )

    def update_conversation(self, conversation_id: str, **body: Any) -> dict[str, Any]:
        return self._http.request(
            "PATCH",
            f"/v1/compare/conversations/{url_quote(conversation_id)}",
            body=body,
        )

    def delete_conversation(self, conversation_id: str) -> dict[str, Any]:
        return self._http.request(
            "DELETE",
            f"/v1/compare/conversations/{url_quote(conversation_id)}",
        )


class AsyncCompareNamespace:
    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def run(
        self,
        *,
        models: list[str],
        prompt: str | None = None,
        dataset_id: str | None = None,
        conversation_id: str | None = None,
        name: str | None = None,
        wait: bool = True,
        timeout_s: float = 600.0,
        interval_s: float = 3.0,
        cancel_event: asyncio.Event | None = None,
        **extra: Any,
    ) -> CompareRun:
        body: dict[str, Any] = {"models": models, **extra}
        if prompt is not None:
            body["prompt"] = prompt
        if dataset_id is not None:
            body["dataset_id"] = dataset_id
        if conversation_id is not None:
            body["conversation_id"] = conversation_id
        if name is not None:
            body["name"] = name

        submitted = await self._http.request("POST", "/v1/compare/runs", body=body)
        if not wait:
            return submitted
        run_id = submitted["id"]

        async def _fetch() -> CompareRun:
            return await self.get_run(run_id)

        return await apoll_until_terminal(
            _fetch,
            _is_compare_terminal,
            timeout_s=timeout_s,
            interval_s=interval_s,
            cancel_event=cancel_event,
        )

    async def list_runs(
        self,
        *,
        limit: int | None = None,
        status: str | None = None,
    ) -> list[CompareRun]:
        res = await self._http.request(
            "GET", "/v1/compare/runs", query={"limit": limit, "status": status}
        )
        return _unwrap_list(res, "runs")

    async def get_run(self, run_id: str) -> CompareRun:
        return await self._http.request(
            "GET", f"/v1/compare/runs/{url_quote(run_id)}"
        )

    async def cancel_run(self, run_id: str) -> CompareRun:
        return await self._http.request(
            "POST", f"/v1/compare/runs/{url_quote(run_id)}/cancel"
        )

    async def save_run(self, run_id: str) -> dict[str, Any]:
        return await self._http.request(
            "POST", f"/v1/compare/runs/{url_quote(run_id)}/save"
        )

    async def mark_winner(self, run_id: str, lane_id: str) -> dict[str, Any]:
        return await self._http.request(
            "POST",
            f"/v1/compare/runs/{url_quote(run_id)}/lanes/{url_quote(lane_id)}/winner",
        )

    async def create_dataset(
        self,
        *,
        name: str,
        test_cases: list[Mapping[str, Any]],
        **extra: Any,
    ) -> dict[str, Any]:
        return await self._http.request(
            "POST",
            "/v1/compare/datasets",
            body={"name": name, "test_cases": list(test_cases), **extra},
        )

    async def list_datasets(self) -> list[dict[str, Any]]:
        res = await self._http.request("GET", "/v1/compare/datasets")
        return _unwrap_list(res, "datasets")

    async def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        return await self._http.request(
            "GET", f"/v1/compare/datasets/{url_quote(dataset_id)}"
        )

    async def create_conversation(self, **params: Any) -> dict[str, Any]:
        return await self._http.request(
            "POST", "/v1/compare/conversations", body=params
        )

    async def list_conversations(self) -> list[dict[str, Any]]:
        res = await self._http.request("GET", "/v1/compare/conversations")
        return _unwrap_list(res, "conversations")

    async def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        return await self._http.request(
            "GET", f"/v1/compare/conversations/{url_quote(conversation_id)}"
        )

    async def add_turn(self, conversation_id: str, **body: Any) -> dict[str, Any]:
        return await self._http.request(
            "POST",
            f"/v1/compare/conversations/{url_quote(conversation_id)}/turns",
            body=body,
        )

    async def update_conversation(self, conversation_id: str, **body: Any) -> dict[str, Any]:
        return await self._http.request(
            "PATCH",
            f"/v1/compare/conversations/{url_quote(conversation_id)}",
            body=body,
        )

    async def delete_conversation(self, conversation_id: str) -> dict[str, Any]:
        return await self._http.request(
            "DELETE",
            f"/v1/compare/conversations/{url_quote(conversation_id)}",
        )


__all__ = ["CompareNamespace", "AsyncCompareNamespace"]
