"""``parel.tasks`` — async generation task polling + cancellation.

Wraps:
    GET  /v1/tasks/{id}
    GET  /v1/tasks
    POST /v1/tasks/{id}/cancel
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable

from .._http import AsyncHttpClient, HttpClient, url_quote
from .._polling import apoll_until_terminal, poll_until_terminal
from ..types import Task, TaskCancelResult

_TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "failed", "cancelled"})


def _is_terminal_task(task: Task) -> bool:
    return str(task.get("status", "")) in _TERMINAL_STATUSES


class TasksNamespace:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def get(self, task_id: str) -> Task:
        return self._http.request("GET", f"/v1/tasks/{url_quote(task_id)}")

    def list(
        self,
        *,
        task_type: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return self._http.request(
            "GET",
            "/v1/tasks",
            query={"task_type": task_type, "status": status, "limit": limit},
        )

    def cancel(self, task_id: str) -> TaskCancelResult:
        """Cancel a pending/processing task and refund credits.

        Already-terminal tasks raise
        :class:`~parel_cloud.errors.ParelTaskNotCancellableError`.
        """
        return self._http.request(
            "POST",
            f"/v1/tasks/{url_quote(task_id)}/cancel",
        )

    def wait_for(
        self,
        task_id: str,
        *,
        timeout_s: float = 300.0,
        interval_s: float = 2.0,
        cancel_event: threading.Event | None = None,
        on_tick: Callable[[Task], None] | None = None,
    ) -> Task:
        """Poll a task until terminal (completed / failed / cancelled)."""
        return poll_until_terminal(
            lambda: self.get(task_id),
            _is_terminal_task,
            timeout_s=timeout_s,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
        )


class AsyncTasksNamespace:
    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def get(self, task_id: str) -> Task:
        return await self._http.request("GET", f"/v1/tasks/{url_quote(task_id)}")

    async def list(
        self,
        *,
        task_type: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return await self._http.request(
            "GET",
            "/v1/tasks",
            query={"task_type": task_type, "status": status, "limit": limit},
        )

    async def cancel(self, task_id: str) -> TaskCancelResult:
        return await self._http.request(
            "POST",
            f"/v1/tasks/{url_quote(task_id)}/cancel",
        )

    async def wait_for(
        self,
        task_id: str,
        *,
        timeout_s: float = 300.0,
        interval_s: float = 2.0,
        cancel_event: asyncio.Event | None = None,
        on_tick: Callable[[Task], Any] | None = None,
    ) -> Task:
        return await apoll_until_terminal(
            lambda: self.get(task_id),
            _is_terminal_task,
            timeout_s=timeout_s,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
        )


__all__ = ["TasksNamespace", "AsyncTasksNamespace"]
