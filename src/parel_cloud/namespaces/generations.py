"""``parel.images`` / ``parel.videos`` / ``parel.audio`` — async generation
helpers.

The gateway submits these jobs onto an SQS queue and returns a
``{task_id, poll_url}`` envelope; the SDK polls under the hood so callers
get a synchronous return. Pass ``wait=False`` to opt into the raw
:class:`TaskSubmission` handle and poll manually.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Mapping

from .._http import AsyncHttpClient, HttpClient, url_quote
from .._polling import apoll_until_terminal, poll_until_terminal
from ..types import Task, TaskSubmission

_TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "failed", "cancelled"})


def _is_submission(value: Any) -> bool:
    return isinstance(value, Mapping) and isinstance(value.get("task_id"), str)


def _is_terminal_task(task: Task) -> bool:
    return str(task.get("status", "")) in _TERMINAL_STATUSES


# -------------------------- sync --------------------------


class _SyncGenerationBase:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def _submit_and_maybe_wait(
        self,
        *,
        path: str,
        body: dict[str, Any],
        wait: bool,
        default_timeout_s: float,
        interval_s: float,
        cancel_event: threading.Event | None,
        on_tick: Callable[[Task], None] | None,
        timeout_s: float | None,
    ) -> Task | TaskSubmission | dict[str, Any]:
        response = self._http.request("POST", path, body=body)
        if not _is_submission(response):
            return response
        if not wait:
            return response
        effective_timeout = timeout_s if timeout_s is not None else default_timeout_s
        task_id = response["task_id"]
        return poll_until_terminal(
            lambda: self._http.request("GET", f"/v1/tasks/{url_quote(task_id)}"),
            _is_terminal_task,
            timeout_s=effective_timeout,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
        )


class ImagesNamespace(_SyncGenerationBase):
    def generate(
        self,
        *,
        model: str,
        prompt: str,
        wait: bool = True,
        timeout_s: float | None = None,
        interval_s: float = 2.0,
        cancel_event: threading.Event | None = None,
        on_tick: Callable[[Task], None] | None = None,
        **extra: Any,
    ) -> Task | TaskSubmission | dict[str, Any]:
        body: dict[str, Any] = {"model": model, "prompt": prompt, **extra}
        return self._submit_and_maybe_wait(
            path="/v1/images/generations",
            body=body,
            wait=wait,
            default_timeout_s=180.0,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
            timeout_s=timeout_s,
        )

    def edit(
        self,
        *,
        model: str,
        image: Any,
        prompt: str,
        wait: bool = True,
        timeout_s: float | None = None,
        interval_s: float = 2.0,
        cancel_event: threading.Event | None = None,
        on_tick: Callable[[Task], None] | None = None,
        **extra: Any,
    ) -> Task | TaskSubmission | dict[str, Any]:
        body: dict[str, Any] = {"model": model, "image": image, "prompt": prompt, **extra}
        return self._submit_and_maybe_wait(
            path="/v1/images/edits",
            body=body,
            wait=wait,
            default_timeout_s=180.0,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
            timeout_s=timeout_s,
        )


class VideosNamespace(_SyncGenerationBase):
    def generate(
        self,
        *,
        model: str,
        prompt: str,
        wait: bool = True,
        timeout_s: float | None = None,
        interval_s: float = 5.0,
        cancel_event: threading.Event | None = None,
        on_tick: Callable[[Task], None] | None = None,
        **extra: Any,
    ) -> Task | TaskSubmission | dict[str, Any]:
        body: dict[str, Any] = {"model": model, "prompt": prompt, **extra}
        return self._submit_and_maybe_wait(
            path="/v1/videos/generations",
            body=body,
            wait=wait,
            default_timeout_s=1800.0,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
            timeout_s=timeout_s,
        )


class AudioNamespace(_SyncGenerationBase):
    def speech(
        self,
        *,
        model: str,
        input: str,
        wait: bool = True,
        timeout_s: float | None = None,
        interval_s: float = 2.0,
        cancel_event: threading.Event | None = None,
        on_tick: Callable[[Task], None] | None = None,
        **extra: Any,
    ) -> Task | TaskSubmission | dict[str, Any]:
        body: dict[str, Any] = {"model": model, "input": input, **extra}
        return self._submit_and_maybe_wait(
            path="/v1/audio/speech",
            body=body,
            wait=wait,
            default_timeout_s=120.0,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
            timeout_s=timeout_s,
        )

    def transcribe(self, **params: Any) -> dict[str, Any]:
        """STT — the gateway returns the transcript synchronously in the
        common JSON-body path. Multipart upload support lands in v0.2.
        """
        return self._http.request("POST", "/v1/audio/transcriptions", body=params)

    def music(
        self,
        *,
        model: str,
        prompt: str,
        wait: bool = True,
        timeout_s: float | None = None,
        interval_s: float = 3.0,
        cancel_event: threading.Event | None = None,
        on_tick: Callable[[Task], None] | None = None,
        **extra: Any,
    ) -> Task | TaskSubmission | dict[str, Any]:
        body: dict[str, Any] = {"model": model, "prompt": prompt, **extra}
        return self._submit_and_maybe_wait(
            path="/v1/audio/music",
            body=body,
            wait=wait,
            default_timeout_s=300.0,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
            timeout_s=timeout_s,
        )


# -------------------------- async --------------------------


class _AsyncGenerationBase:
    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def _submit_and_maybe_wait(
        self,
        *,
        path: str,
        body: dict[str, Any],
        wait: bool,
        default_timeout_s: float,
        interval_s: float,
        cancel_event: asyncio.Event | None,
        on_tick: Callable[[Task], Any] | None,
        timeout_s: float | None,
    ) -> Task | TaskSubmission | dict[str, Any]:
        response = await self._http.request("POST", path, body=body)
        if not _is_submission(response):
            return response
        if not wait:
            return response
        effective_timeout = timeout_s if timeout_s is not None else default_timeout_s
        task_id = response["task_id"]

        async def _fetch() -> Task:
            return await self._http.request("GET", f"/v1/tasks/{url_quote(task_id)}")

        return await apoll_until_terminal(
            _fetch,
            _is_terminal_task,
            timeout_s=effective_timeout,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
        )


class AsyncImagesNamespace(_AsyncGenerationBase):
    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        wait: bool = True,
        timeout_s: float | None = None,
        interval_s: float = 2.0,
        cancel_event: asyncio.Event | None = None,
        on_tick: Callable[[Task], Any] | None = None,
        **extra: Any,
    ) -> Task | TaskSubmission | dict[str, Any]:
        body: dict[str, Any] = {"model": model, "prompt": prompt, **extra}
        return await self._submit_and_maybe_wait(
            path="/v1/images/generations",
            body=body,
            wait=wait,
            default_timeout_s=180.0,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
            timeout_s=timeout_s,
        )

    async def edit(
        self,
        *,
        model: str,
        image: Any,
        prompt: str,
        wait: bool = True,
        timeout_s: float | None = None,
        interval_s: float = 2.0,
        cancel_event: asyncio.Event | None = None,
        on_tick: Callable[[Task], Any] | None = None,
        **extra: Any,
    ) -> Task | TaskSubmission | dict[str, Any]:
        body: dict[str, Any] = {"model": model, "image": image, "prompt": prompt, **extra}
        return await self._submit_and_maybe_wait(
            path="/v1/images/edits",
            body=body,
            wait=wait,
            default_timeout_s=180.0,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
            timeout_s=timeout_s,
        )


class AsyncVideosNamespace(_AsyncGenerationBase):
    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        wait: bool = True,
        timeout_s: float | None = None,
        interval_s: float = 5.0,
        cancel_event: asyncio.Event | None = None,
        on_tick: Callable[[Task], Any] | None = None,
        **extra: Any,
    ) -> Task | TaskSubmission | dict[str, Any]:
        body: dict[str, Any] = {"model": model, "prompt": prompt, **extra}
        return await self._submit_and_maybe_wait(
            path="/v1/videos/generations",
            body=body,
            wait=wait,
            default_timeout_s=1800.0,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
            timeout_s=timeout_s,
        )


class AsyncAudioNamespace(_AsyncGenerationBase):
    async def speech(
        self,
        *,
        model: str,
        input: str,
        wait: bool = True,
        timeout_s: float | None = None,
        interval_s: float = 2.0,
        cancel_event: asyncio.Event | None = None,
        on_tick: Callable[[Task], Any] | None = None,
        **extra: Any,
    ) -> Task | TaskSubmission | dict[str, Any]:
        body: dict[str, Any] = {"model": model, "input": input, **extra}
        return await self._submit_and_maybe_wait(
            path="/v1/audio/speech",
            body=body,
            wait=wait,
            default_timeout_s=120.0,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
            timeout_s=timeout_s,
        )

    async def transcribe(self, **params: Any) -> dict[str, Any]:
        return await self._http.request("POST", "/v1/audio/transcriptions", body=params)

    async def music(
        self,
        *,
        model: str,
        prompt: str,
        wait: bool = True,
        timeout_s: float | None = None,
        interval_s: float = 3.0,
        cancel_event: asyncio.Event | None = None,
        on_tick: Callable[[Task], Any] | None = None,
        **extra: Any,
    ) -> Task | TaskSubmission | dict[str, Any]:
        body: dict[str, Any] = {"model": model, "prompt": prompt, **extra}
        return await self._submit_and_maybe_wait(
            path="/v1/audio/music",
            body=body,
            wait=wait,
            default_timeout_s=300.0,
            interval_s=interval_s,
            cancel_event=cancel_event,
            on_tick=on_tick,
            timeout_s=timeout_s,
        )


__all__ = [
    "ImagesNamespace",
    "VideosNamespace",
    "AudioNamespace",
    "AsyncImagesNamespace",
    "AsyncVideosNamespace",
    "AsyncAudioNamespace",
]
