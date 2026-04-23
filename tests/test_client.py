"""Parel + AsyncParel client construction tests."""

from __future__ import annotations

import pytest

from parel_cloud import AsyncParel, Parel, ParelConfigError


def test_missing_api_key_raises_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PAREL_API_KEY", raising=False)
    with pytest.raises(ParelConfigError):
        Parel()


def test_env_var_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAREL_API_KEY", "env-key")
    parel = Parel()
    try:
        assert parel.api_key == "env-key"
    finally:
        parel.close()


def test_base_url_trims_trailing_slash() -> None:
    parel = Parel(api_key="k", base_url="https://api.example.com/")
    try:
        assert parel.base_url == "https://api.example.com"
    finally:
        parel.close()


def test_base_url_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAREL_BASE_URL", "https://staging.parel.test")
    parel = Parel(api_key="k")
    try:
        assert parel.base_url == "https://staging.parel.test"
    finally:
        parel.close()


def test_namespaces_attached() -> None:
    parel = Parel(api_key="k")
    try:
        for name in (
            "credits",
            "models",
            "tasks",
            "images",
            "videos",
            "audio",
            "gpu",
            "compare",
        ):
            assert hasattr(parel, name), f"Parel missing namespace: {name}"
    finally:
        parel.close()


def test_sync_context_manager() -> None:
    with Parel(api_key="k") as parel:
        assert parel.api_key == "k"


async def test_async_context_manager() -> None:
    async with AsyncParel(api_key="k") as parel:
        assert parel.api_key == "k"


async def test_async_namespaces_attached() -> None:
    async with AsyncParel(api_key="k") as parel:
        for name in (
            "credits",
            "models",
            "tasks",
            "images",
            "videos",
            "audio",
            "gpu",
            "compare",
        ):
            assert hasattr(parel, name)
