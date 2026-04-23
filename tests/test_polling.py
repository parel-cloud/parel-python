"""Polling helpers — sync + async."""

from __future__ import annotations

import asyncio
import threading

import pytest

from parel_cloud import ParelTimeoutError
from parel_cloud._polling import apoll_until_terminal, poll_until_terminal


def test_sync_returns_first_terminal_value() -> None:
    sequence = iter([{"status": "pending"}, {"status": "processing"}, {"status": "completed"}])
    result = poll_until_terminal(
        lambda: next(sequence),
        lambda v: v["status"] == "completed",
        timeout_s=2.0,
        interval_s=0.01,
    )
    assert result["status"] == "completed"


def test_sync_timeout() -> None:
    with pytest.raises(ParelTimeoutError):
        poll_until_terminal(
            lambda: {"status": "pending"},
            lambda v: v["status"] == "completed",
            timeout_s=0.1,
            interval_s=0.02,
        )


def test_sync_cancel_event_aborts() -> None:
    event = threading.Event()

    def fetcher() -> dict[str, str]:
        event.set()
        return {"status": "pending"}

    with pytest.raises(ParelTimeoutError):
        poll_until_terminal(
            fetcher,
            lambda v: v["status"] == "completed",
            timeout_s=2.0,
            interval_s=0.01,
            cancel_event=event,
        )


def test_sync_on_tick_fires_each_iteration() -> None:
    seen: list[int] = []
    n = {"i": 0}

    def fetcher() -> dict[str, int]:
        n["i"] += 1
        return {"status": "completed" if n["i"] > 2 else "pending", "i": n["i"]}

    poll_until_terminal(
        fetcher,
        lambda v: v["status"] == "completed",
        timeout_s=2.0,
        interval_s=0.01,
        on_tick=lambda v: seen.append(v["i"]),
    )
    assert seen == [1, 2, 3]


async def test_async_returns_first_terminal_value() -> None:
    values = [{"status": "pending"}, {"status": "completed"}]

    async def fetcher() -> dict[str, str]:
        return values.pop(0)

    result = await apoll_until_terminal(
        fetcher,
        lambda v: v["status"] == "completed",
        timeout_s=2.0,
        interval_s=0.01,
    )
    assert result["status"] == "completed"


async def test_async_timeout() -> None:
    async def fetcher() -> dict[str, str]:
        return {"status": "pending"}

    with pytest.raises(ParelTimeoutError):
        await apoll_until_terminal(
            fetcher,
            lambda v: v["status"] == "completed",
            timeout_s=0.1,
            interval_s=0.02,
        )


async def test_async_cancel_event_aborts() -> None:
    cancel = asyncio.Event()

    async def fetcher() -> dict[str, str]:
        cancel.set()
        return {"status": "pending"}

    with pytest.raises(ParelTimeoutError):
        await apoll_until_terminal(
            fetcher,
            lambda v: v["status"] == "completed",
            timeout_s=2.0,
            interval_s=0.05,
            cancel_event=cancel,
        )
