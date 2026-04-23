"""``parel.models`` — list + retrieve available models.

Wraps:
    GET /v1/models
    GET /v1/models/{id}
"""

from __future__ import annotations

from .._http import AsyncHttpClient, HttpClient, url_quote
from ..types import ModelInfo, ModelListResponse


class ModelsNamespace:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self) -> ModelListResponse:
        """Full catalogue available to the current tenant."""
        return self._http.request("GET", "/v1/models")

    def retrieve(self, model_id: str) -> ModelInfo:
        """Detail for a single model."""
        return self._http.request("GET", f"/v1/models/{url_quote(model_id)}")


class AsyncModelsNamespace:
    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def list(self) -> ModelListResponse:
        return await self._http.request("GET", "/v1/models")

    async def retrieve(self, model_id: str) -> ModelInfo:
        return await self._http.request("GET", f"/v1/models/{url_quote(model_id)}")


__all__ = ["ModelsNamespace", "AsyncModelsNamespace"]
