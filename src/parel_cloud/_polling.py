"""Generic polling helpers used by task-bound namespaces (images, videos,
audio, GPU lifecycle, compare runs).

Callers supply a fetcher + terminal-state predicate; the helper drives the
loop with jittered interval and a hard deadline, then returns the final
value or raises :class:`ParelTimeoutError`.

Sync and async variants share the same argument surface.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Awaitable, Callable, TypeVar

from .errors import ParelTimeoutError

T = TypeVar("T")

_DEFAULT_INTERVAL_S = 2.0
_DEFAULT_MAX_INTERVAL_S = 10.0


def poll_until_terminal(
    fetcher: Callable[[], T],
    is_terminal: Callable[[T], bool],
    *,
    timeout_s: float,
    interval_s: float = _DEFAULT_INTERVAL_S,
    max_interval_s: float = _DEFAULT_MAX_INTERVAL_S,
    interval_multiplier: float = 1.0,
    cancel_event: threading.Event | None = None,
    on_tick: Callable[[T], None] | None = None,
) -> T:
    """Poll ``fetcher`` until ``is_terminal`` returns True or the deadline
    expires (in which case :class:`ParelTimeoutError` is raised).

    The interval may grow after each poll via ``interval_multiplier`` (set to
    >1.0 for exponential backoff), capped at ``max_interval_s``.
    """

    deadline = time.monotonic() + timeout_s
    current_interval = interval_s

    while True:
        if cancel_event is not None and cancel_event.is_set():
            raise ParelTimeoutError("polling aborted")

        value = fetcher()
        if on_tick is not None:
            on_tick(value)
        if is_terminal(value):
            return value

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ParelTimeoutError(
                f"Polling did not reach terminal state within {timeout_s}s"
            )

        wait = min(current_interval, max(remaining, 0.05))
        if cancel_event is not None:
            if cancel_event.wait(wait):
                raise ParelTimeoutError("polling aborted")
        else:
            time.sleep(wait)
        current_interval = min(current_interval * interval_multiplier, max_interval_s)


async def apoll_until_terminal(
    fetcher: Callable[[], Awaitable[T]],
    is_terminal: Callable[[T], bool],
    *,
    timeout_s: float,
    interval_s: float = _DEFAULT_INTERVAL_S,
    max_interval_s: float = _DEFAULT_MAX_INTERVAL_S,
    interval_multiplier: float = 1.0,
    cancel_event: asyncio.Event | None = None,
    on_tick: Callable[[T], Any] | None = None,
) -> T:
    """Async counterpart of :func:`poll_until_terminal`."""

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    current_interval = interval_s

    while True:
        if cancel_event is not None and cancel_event.is_set():
            raise ParelTimeoutError("polling aborted")

        value = await fetcher()
        if on_tick is not None:
            result = on_tick(value)
            if asyncio.iscoroutine(result):
                await result
        if is_terminal(value):
            return value

        remaining = deadline - loop.time()
        if remaining <= 0:
            raise ParelTimeoutError(
                f"Polling did not reach terminal state within {timeout_s}s"
            )

        wait = min(current_interval, max(remaining, 0.05))
        if cancel_event is not None:
            try:
                await asyncio.wait_for(cancel_event.wait(), timeout=wait)
            except asyncio.TimeoutError:
                pass
            else:
                raise ParelTimeoutError("polling aborted")
        else:
            await asyncio.sleep(wait)
        current_interval = min(current_interval * interval_multiplier, max_interval_s)


__all__ = ["poll_until_terminal", "apoll_until_terminal"]
