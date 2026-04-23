"""``parel.openai`` — the official ``openai`` Python SDK pointed at Parel.

Rather than re-wrap OpenAI's types, the SDK lazily instantiates the official
client with ``base_url`` pointing at Parel's gateway. Users get streaming,
tools, vision, audio and the full OpenAI type surface for free while
requests hit ``api.parel.cloud``.

``openai`` is an optional peer dependency — install via
``pip install parel-cloud[openai]``.

Usage (sync)::

    client = parel.openai  # an `openai.OpenAI` instance
    client.chat.completions.create(model="qwen3.5-72b", messages=[...])

Usage (async)::

    client = await async_parel.openai  # an `openai.AsyncOpenAI` instance
    await client.chat.completions.create(model="qwen3.5-72b", messages=[...])
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable

from ..errors import ParelConfigError


def _raise_missing_openai(err: Exception) -> None:
    raise ParelConfigError(
        "The 'openai' peer dependency is required for parel.openai. "
        "Install it with `pip install parel-cloud[openai]`. "
        f"Underlying error: {err}"
    ) from err


@lru_cache(maxsize=1)
def _sync_ctor() -> Callable[..., Any]:
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except ImportError as err:  # pragma: no cover — depends on env
        _raise_missing_openai(err)
        raise  # unreachable, satisfies type checker
    return OpenAI


@lru_cache(maxsize=1)
def _async_ctor() -> Callable[..., Any]:
    try:
        from openai import AsyncOpenAI  # type: ignore[import-not-found]
    except ImportError as err:  # pragma: no cover
        _raise_missing_openai(err)
        raise
    return AsyncOpenAI


def create_openai_sync(*, api_key: str, base_url: str) -> Any:
    """Return an ``openai.OpenAI`` instance configured for Parel."""
    ctor = _sync_ctor()
    return ctor(api_key=api_key, base_url=f"{base_url}/v1")


def create_openai_async(*, api_key: str, base_url: str) -> Any:
    """Return an ``openai.AsyncOpenAI`` instance configured for Parel."""
    ctor = _async_ctor()
    return ctor(api_key=api_key, base_url=f"{base_url}/v1")


def _reset_openai_factory_cache() -> None:
    """Reset cached ctors. Useful for tests."""
    _sync_ctor.cache_clear()
    _async_ctor.cache_clear()


__all__ = [
    "create_openai_sync",
    "create_openai_async",
]
