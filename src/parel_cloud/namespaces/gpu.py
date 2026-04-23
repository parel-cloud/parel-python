"""``parel.gpu`` — BYOM (bring-your-own-model) GPU deployment lifecycle.

Wraps the ``/v1/deployments/*``, ``/v1/gpu-tiers*`` and ``/v1/hf/*`` route
surface. Full CRUD, lifecycle actions, inference proxy, and a
``wait_for_running`` polling helper.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Mapping

from .._http import AsyncHttpClient, HttpClient, url_quote
from .._polling import apoll_until_terminal, poll_until_terminal
from ..types import Deployment, GpuTier, HfValidateResponse, PrefetchStatus

_RUNNING_TERMINAL: frozenset[str] = frozenset({"running", "error", "stopped", "crashed"})


def _unwrap_list(payload: Any, key: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, Mapping) and isinstance(payload.get(key), list):
        return payload[key]
    return []


def _is_deployment_terminal(dep: Deployment) -> bool:
    return str(dep.get("status", "")) in _RUNNING_TERMINAL


class GpuNamespace:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    # ---------------------- lifecycle ----------------------

    def list(self) -> list[Deployment]:
        res = self._http.request("GET", "/v1/deployments")
        return _unwrap_list(res, "deployments")

    def create(self, **params: Any) -> Deployment:
        return self._http.request("POST", "/v1/deployments", body=params)

    def get(self, deployment_id: str) -> Deployment:
        return self._http.request("GET", f"/v1/deployments/{url_quote(deployment_id)}")

    def start(self, deployment_id: str) -> Deployment:
        return self._http.request(
            "POST", f"/v1/deployments/{url_quote(deployment_id)}/start"
        )

    def stop(self, deployment_id: str) -> Deployment:
        return self._http.request(
            "POST", f"/v1/deployments/{url_quote(deployment_id)}/stop"
        )

    def delete(self, deployment_id: str) -> dict[str, Any]:
        return self._http.request(
            "DELETE", f"/v1/deployments/{url_quote(deployment_id)}"
        )

    # ---------------------- telemetry ----------------------

    def events(self, deployment_id: str) -> dict[str, Any]:
        return self._http.request(
            "GET", f"/v1/deployments/{url_quote(deployment_id)}/events"
        )

    def metrics(self, deployment_id: str) -> dict[str, Any]:
        return self._http.request(
            "GET", f"/v1/deployments/{url_quote(deployment_id)}/metrics"
        )

    def billing(self, deployment_id: str) -> dict[str, Any]:
        return self._http.request(
            "GET", f"/v1/deployments/{url_quote(deployment_id)}/billing"
        )

    # ---------------------- inference ----------------------

    def chat(self, deployment_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
        """Send a ``chat.completions``-style request to a BYOM deployment."""
        return self._http.request(
            "POST",
            f"/v1/deployments/{url_quote(deployment_id)}/chat/completions",
            body=dict(body),
        )

    # ---------------------- tiers / preview ----------------------

    def tiers(self) -> list[GpuTier]:
        res = self._http.request("GET", "/v1/gpu-tiers")
        return _unwrap_list(res, "tiers")

    def tiers_live(self) -> list[GpuTier]:
        res = self._http.request("GET", "/v1/gpu-tiers/live")
        return _unwrap_list(res, "tiers")

    def preview(
        self,
        *,
        huggingface_id: str,
        gpu_tier: str | None = None,
    ) -> dict[str, Any]:
        return self._http.request(
            "GET",
            "/v1/deployments/preview",
            query={"huggingface_id": huggingface_id, "gpu_tier": gpu_tier},
        )

    # ---------------------- HF validate + prefetch ----------------------

    def validate_huggingface(self, huggingface_id: str) -> HfValidateResponse:
        return self._http.request(
            "POST",
            "/v1/hf/validate",
            body={"huggingface_id": huggingface_id},
        )

    def prefetch(self, huggingface_id: str) -> dict[str, Any]:
        return self._http.request(
            "POST",
            "/v1/deployments/prefetch",
            body={"huggingface_id": huggingface_id},
        )

    def prefetch_status(self, huggingface_id: str) -> PrefetchStatus:
        return self._http.request(
            "GET",
            f"/v1/deployments/prefetch/{url_quote(huggingface_id)}",
        )

    def cancel_prefetch(self, huggingface_id: str) -> dict[str, Any]:
        return self._http.request(
            "POST",
            f"/v1/deployments/prefetch/{url_quote(huggingface_id)}/cancel",
        )

    # ---------------------- polling helper ----------------------

    def wait_for_running(
        self,
        deployment_id: str,
        *,
        timeout_s: float = 900.0,
        interval_s: float = 10.0,
        cancel_event: threading.Event | None = None,
        on_tick: Callable[[Deployment], None] | None = None,
    ) -> Deployment:
        return poll_until_terminal(
            lambda: self.get(deployment_id),
            _is_deployment_terminal,
            timeout_s=timeout_s,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
        )


class AsyncGpuNamespace:
    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def list(self) -> list[Deployment]:
        res = await self._http.request("GET", "/v1/deployments")
        return _unwrap_list(res, "deployments")

    async def create(self, **params: Any) -> Deployment:
        return await self._http.request("POST", "/v1/deployments", body=params)

    async def get(self, deployment_id: str) -> Deployment:
        return await self._http.request(
            "GET", f"/v1/deployments/{url_quote(deployment_id)}"
        )

    async def start(self, deployment_id: str) -> Deployment:
        return await self._http.request(
            "POST", f"/v1/deployments/{url_quote(deployment_id)}/start"
        )

    async def stop(self, deployment_id: str) -> Deployment:
        return await self._http.request(
            "POST", f"/v1/deployments/{url_quote(deployment_id)}/stop"
        )

    async def delete(self, deployment_id: str) -> dict[str, Any]:
        return await self._http.request(
            "DELETE", f"/v1/deployments/{url_quote(deployment_id)}"
        )

    async def events(self, deployment_id: str) -> dict[str, Any]:
        return await self._http.request(
            "GET", f"/v1/deployments/{url_quote(deployment_id)}/events"
        )

    async def metrics(self, deployment_id: str) -> dict[str, Any]:
        return await self._http.request(
            "GET", f"/v1/deployments/{url_quote(deployment_id)}/metrics"
        )

    async def billing(self, deployment_id: str) -> dict[str, Any]:
        return await self._http.request(
            "GET", f"/v1/deployments/{url_quote(deployment_id)}/billing"
        )

    async def chat(self, deployment_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
        return await self._http.request(
            "POST",
            f"/v1/deployments/{url_quote(deployment_id)}/chat/completions",
            body=dict(body),
        )

    async def tiers(self) -> list[GpuTier]:
        res = await self._http.request("GET", "/v1/gpu-tiers")
        return _unwrap_list(res, "tiers")

    async def tiers_live(self) -> list[GpuTier]:
        res = await self._http.request("GET", "/v1/gpu-tiers/live")
        return _unwrap_list(res, "tiers")

    async def preview(
        self,
        *,
        huggingface_id: str,
        gpu_tier: str | None = None,
    ) -> dict[str, Any]:
        return await self._http.request(
            "GET",
            "/v1/deployments/preview",
            query={"huggingface_id": huggingface_id, "gpu_tier": gpu_tier},
        )

    async def validate_huggingface(self, huggingface_id: str) -> HfValidateResponse:
        return await self._http.request(
            "POST",
            "/v1/hf/validate",
            body={"huggingface_id": huggingface_id},
        )

    async def prefetch(self, huggingface_id: str) -> dict[str, Any]:
        return await self._http.request(
            "POST",
            "/v1/deployments/prefetch",
            body={"huggingface_id": huggingface_id},
        )

    async def prefetch_status(self, huggingface_id: str) -> PrefetchStatus:
        return await self._http.request(
            "GET",
            f"/v1/deployments/prefetch/{url_quote(huggingface_id)}",
        )

    async def cancel_prefetch(self, huggingface_id: str) -> dict[str, Any]:
        return await self._http.request(
            "POST",
            f"/v1/deployments/prefetch/{url_quote(huggingface_id)}/cancel",
        )

    async def wait_for_running(
        self,
        deployment_id: str,
        *,
        timeout_s: float = 900.0,
        interval_s: float = 10.0,
        cancel_event: asyncio.Event | None = None,
        on_tick: Callable[[Deployment], Any] | None = None,
    ) -> Deployment:
        async def _fetch() -> Deployment:
            return await self.get(deployment_id)

        return await apoll_until_terminal(
            _fetch,
            _is_deployment_terminal,
            timeout_s=timeout_s,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
        )


__all__ = ["GpuNamespace", "AsyncGpuNamespace"]
