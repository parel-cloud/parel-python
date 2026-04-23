"""Parel SDK for Python.

Quick start::

    from parel_cloud import Parel

    parel = Parel(api_key="...")
    snapshot = parel.credits.get()
    print(snapshot["remaining_usd"])

Async::

    import asyncio
    from parel_cloud import AsyncParel

    async def main():
        async with AsyncParel() as parel:
            models = await parel.models.list()
            print(len(models["data"]))

    asyncio.run(main())

Full reference: https://github.com/parel-cloud/parel-python
"""

from __future__ import annotations

__version__ = "0.1.0"

from .client import AsyncParel, Parel
from .errors import (
    ParelAPIError,
    ParelAuthenticationError,
    ParelBudgetExceededError,
    ParelCapacityExhaustedError,
    ParelConfigError,
    ParelConflictError,
    ParelConnectionError,
    ParelDeploymentFailedError,
    ParelDeploymentNotReadyError,
    ParelError,
    ParelNotFoundError,
    ParelPermissionError,
    ParelPiiBlockedError,
    ParelProviderError,
    ParelRateLimitError,
    ParelServerError,
    ParelTaskNotCancellableError,
    ParelTimeoutError,
    ParelValidationError,
    parse_http_error,
)

__all__ = [
    "__version__",
    "Parel",
    "AsyncParel",
    # Errors
    "ParelError",
    "ParelAPIError",
    "ParelConfigError",
    "ParelConnectionError",
    "ParelTimeoutError",
    "ParelAuthenticationError",
    "ParelPermissionError",
    "ParelNotFoundError",
    "ParelConflictError",
    "ParelValidationError",
    "ParelRateLimitError",
    "ParelBudgetExceededError",
    "ParelServerError",
    "ParelTaskNotCancellableError",
    "ParelPiiBlockedError",
    "ParelCapacityExhaustedError",
    "ParelDeploymentNotReadyError",
    "ParelDeploymentFailedError",
    "ParelProviderError",
    "parse_http_error",
]
