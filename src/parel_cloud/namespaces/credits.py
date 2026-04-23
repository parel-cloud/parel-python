"""``parel.credits`` — budget snapshot (remaining / limit / spent).

Wraps:
    GET /v1/usage/budget
"""

from __future__ import annotations

from .._http import AsyncHttpClient, HttpClient
from ..types import BudgetSnapshot


class CreditsNamespace:
    """Blocking ``parel.credits`` namespace."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def get(self) -> BudgetSnapshot:
        """Current budget snapshot: ``limit_usd``, ``spent_usd``, ``remaining_usd``."""
        return self._http.request("GET", "/v1/usage/budget")


class AsyncCreditsNamespace:
    """Async ``parel.credits`` namespace."""

    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def get(self) -> BudgetSnapshot:
        return await self._http.request("GET", "/v1/usage/budget")


__all__ = ["CreditsNamespace", "AsyncCreditsNamespace"]
