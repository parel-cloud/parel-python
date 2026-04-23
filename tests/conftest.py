"""Pytest fixtures shared across test modules."""

from __future__ import annotations

import pytest

from parel_cloud import AsyncParel, Parel


@pytest.fixture
def parel() -> Parel:
    return Parel(api_key="test-key", base_url="https://api.parel.test")


@pytest.fixture
async def async_parel() -> AsyncParel:
    client = AsyncParel(api_key="test-key", base_url="https://api.parel.test")
    try:
        yield client
    finally:
        await client.aclose()
