"""Parel SDK root clients.

Two entry points, feature-equivalent:

* :class:`Parel` — blocking; wraps :class:`httpx.Client`.
* :class:`AsyncParel` — asyncio; wraps :class:`httpx.AsyncClient`.

Each instance composes the HTTP layer with all namespaces::

    parel = Parel(api_key=os.environ["PAREL_API_KEY"])
    credits = parel.credits.get()
    parel.tasks.cancel(task_id)
    parel.openai.chat.completions.create(model="qwen3.5-72b", ...)
"""

from __future__ import annotations

import os
from typing import Any

from ._http import AsyncHttpClient, HttpClient
from .errors import ParelConfigError
from .namespaces import (
    AsyncAudioNamespace,
    AsyncCompareNamespace,
    AsyncCreditsNamespace,
    AsyncGpuNamespace,
    AsyncImagesNamespace,
    AsyncModelsNamespace,
    AsyncTasksNamespace,
    AsyncVideosNamespace,
    AudioNamespace,
    CompareNamespace,
    CreditsNamespace,
    GpuNamespace,
    ImagesNamespace,
    ModelsNamespace,
    TasksNamespace,
    VideosNamespace,
)
from .namespaces.openai import create_openai_async, create_openai_sync

DEFAULT_BASE_URL = "https://api.parel.cloud"
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_MAX_RETRIES = 2


def _resolve_api_key(api_key: str | None) -> str:
    if api_key:
        return api_key
    env = os.environ.get("PAREL_API_KEY")
    if env:
        return env
    raise ParelConfigError(
        "Parel SDK: missing API key. Pass `api_key=...` or set the "
        "PAREL_API_KEY environment variable."
    )


def _resolve_base_url(base_url: str | None) -> str:
    if base_url:
        return base_url.rstrip("/")
    env = os.environ.get("PAREL_BASE_URL")
    return (env or DEFAULT_BASE_URL).rstrip("/")


class Parel:
    """Synchronous Parel client.

    Parameters
    ----------
    api_key:
        Bearer token. Falls back to ``PAREL_API_KEY`` env var.
    base_url:
        Gateway base URL. Defaults to ``https://api.parel.cloud`` (or
        ``PAREL_BASE_URL`` env var).
    timeout_s:
        Per-request timeout, seconds. Default 60.
    max_retries:
        Retries on 429 / 5xx / transport errors for idempotent verbs.
        Default 2.
    user_agent:
        Extra ``User-Agent`` suffix appended to the default.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
        user_agent: str | None = None,
    ) -> None:
        resolved_key = _resolve_api_key(api_key)
        resolved_base = _resolve_base_url(base_url)

        self.api_key = resolved_key
        self.base_url = resolved_base
        self.http = HttpClient(
            api_key=resolved_key,
            base_url=resolved_base,
            timeout_s=timeout_s,
            max_retries=max_retries,
            user_agent=user_agent,
        )

        self.credits = CreditsNamespace(self.http)
        self.models = ModelsNamespace(self.http)
        self.tasks = TasksNamespace(self.http)
        self.images = ImagesNamespace(self.http)
        self.videos = VideosNamespace(self.http)
        self.audio = AudioNamespace(self.http)
        self.gpu = GpuNamespace(self.http)
        self.compare = CompareNamespace(self.http)

        self._openai_client: Any | None = None

    @property
    def openai(self) -> Any:
        """Lazily build and cache an ``openai.OpenAI`` client pointed at
        Parel's gateway. Requires ``pip install parel-cloud[openai]``.
        """
        if self._openai_client is None:
            self._openai_client = create_openai_sync(
                api_key=self.api_key, base_url=self.base_url
            )
        return self._openai_client

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> Parel:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class AsyncParel:
    """Asyncio Parel client. Same surface as :class:`Parel`, but every
    namespace method returns an awaitable.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
        user_agent: str | None = None,
    ) -> None:
        resolved_key = _resolve_api_key(api_key)
        resolved_base = _resolve_base_url(base_url)

        self.api_key = resolved_key
        self.base_url = resolved_base
        self.http = AsyncHttpClient(
            api_key=resolved_key,
            base_url=resolved_base,
            timeout_s=timeout_s,
            max_retries=max_retries,
            user_agent=user_agent,
        )

        self.credits = AsyncCreditsNamespace(self.http)
        self.models = AsyncModelsNamespace(self.http)
        self.tasks = AsyncTasksNamespace(self.http)
        self.images = AsyncImagesNamespace(self.http)
        self.videos = AsyncVideosNamespace(self.http)
        self.audio = AsyncAudioNamespace(self.http)
        self.gpu = AsyncGpuNamespace(self.http)
        self.compare = AsyncCompareNamespace(self.http)

        self._openai_client: Any | None = None

    @property
    def openai(self) -> Any:
        """Lazily build and cache an ``openai.AsyncOpenAI`` client pointed at
        Parel's gateway. Requires ``pip install parel-cloud[openai]``.
        """
        if self._openai_client is None:
            self._openai_client = create_openai_async(
                api_key=self.api_key, base_url=self.base_url
            )
        return self._openai_client

    async def aclose(self) -> None:
        await self.http.aclose()

    async def __aenter__(self) -> AsyncParel:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()


__all__ = ["Parel", "AsyncParel", "DEFAULT_BASE_URL"]
