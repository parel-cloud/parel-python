"""Parel SDK error hierarchy.

The base class :class:`ParelError` carries the standard OpenAI-compatible
error envelope fields (``message``, ``type``, ``code``, ``status``,
``request_id``, ``param``). HTTP-status-specific subclasses enable
``isinstance`` checks in user code:

    try:
        parel.images.generate(...)
    except ParelRateLimitError:
        ...
    except ParelBudgetExceededError:
        ...

The hierarchy is the direct Python port of ``@parel-cloud/node``'s
``src/errors.ts``. Keep the two files in sync when adding new error codes.
"""

from __future__ import annotations

from typing import Any, Mapping


class ParelError(Exception):
    """Base class for all SDK errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        type: str | None = None,
        status: int | None = None,
        request_id: str | None = None,
        param: str | None = None,
        retry_after: float | None = None,
        raw: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.type = type
        self.status = status
        self.request_id = request_id
        self.param = param
        self.retry_after = retry_after
        self.raw = raw

    def __str__(self) -> str:
        parts = [self.message]
        meta: list[str] = []
        if self.status is not None:
            meta.append(f"status={self.status}")
        if self.code:
            meta.append(f"code={self.code}")
        if self.request_id:
            meta.append(f"request_id={self.request_id}")
        if meta:
            parts.append(f"({', '.join(meta)})")
        return " ".join(parts)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.message!r}, code={self.code!r}, status={self.status!r})"


class ParelConfigError(ParelError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="config_error")


class ParelTimeoutError(ParelError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="timeout")


class ParelConnectionError(ParelError):
    def __init__(self, message: str, cause: Any = None) -> None:
        super().__init__(message, code="connection_error", raw=cause)


class ParelAPIError(ParelError):
    """Generic HTTP error. Raised when no more specific subclass matches."""


class ParelAuthenticationError(ParelError):
    def __init__(self, message: str, **opts: Any) -> None:
        opts.setdefault("status", 401)
        super().__init__(message, **opts)


class ParelPermissionError(ParelError):
    def __init__(self, message: str, **opts: Any) -> None:
        opts.setdefault("status", 403)
        super().__init__(message, **opts)


class ParelNotFoundError(ParelError):
    def __init__(self, message: str, **opts: Any) -> None:
        opts.setdefault("status", 404)
        super().__init__(message, **opts)


class ParelConflictError(ParelError):
    def __init__(self, message: str, **opts: Any) -> None:
        opts.setdefault("status", 409)
        super().__init__(message, **opts)


class ParelValidationError(ParelError):
    def __init__(self, message: str, **opts: Any) -> None:
        opts.setdefault("status", 400)
        super().__init__(message, **opts)


class ParelRateLimitError(ParelError):
    def __init__(self, message: str, **opts: Any) -> None:
        opts.setdefault("status", 429)
        super().__init__(message, **opts)


class ParelBudgetExceededError(ParelError):
    def __init__(self, message: str, **opts: Any) -> None:
        opts.setdefault("status", 402)
        super().__init__(message, **opts)


class ParelServerError(ParelError):
    def __init__(self, message: str, **opts: Any) -> None:
        opts.setdefault("status", 500)
        super().__init__(message, **opts)


# --------------------------------------------------------------------------
# Code-specific refinements. Status-inherited from their parent so that
# `except ParelConflictError` still catches ParelTaskNotCancellableError etc.
# --------------------------------------------------------------------------


class ParelTaskNotCancellableError(ParelConflictError):
    def __init__(self, message: str, **opts: Any) -> None:
        opts.setdefault("code", "task_not_cancellable")
        super().__init__(message, **opts)


class ParelPiiBlockedError(ParelValidationError):
    def __init__(self, message: str, **opts: Any) -> None:
        opts.setdefault("code", "pii_blocked")
        super().__init__(message, **opts)


class ParelCapacityExhaustedError(ParelServerError):
    def __init__(self, message: str, **opts: Any) -> None:
        opts.setdefault("status", 503)
        opts.setdefault("code", "capacity_exhausted")
        super().__init__(message, **opts)


class ParelDeploymentNotReadyError(ParelConflictError):
    def __init__(self, message: str, **opts: Any) -> None:
        opts.setdefault("code", "deployment_not_ready")
        super().__init__(message, **opts)


class ParelDeploymentFailedError(ParelError):
    def __init__(self, message: str, **opts: Any) -> None:
        opts.setdefault("status", 502)
        opts.setdefault("code", "deployment_failed")
        super().__init__(message, **opts)


class ParelProviderError(ParelError):
    def __init__(self, message: str, **opts: Any) -> None:
        opts.setdefault("status", 502)
        opts.setdefault("code", "provider_error")
        super().__init__(message, **opts)


def parse_http_error(
    status: int,
    body: Any,
    headers: Mapping[str, str] | None = None,
) -> ParelError:
    """Convert a gateway HTTP error response into a typed :class:`ParelError`.

    Expects an OpenAI-compatible envelope::

        {"error": {"message": ..., "type": ..., "code": ..., "param": ...}}

    Resolution order:
      1. Match on ``error.code`` (task_not_cancellable, pii_blocked,
         capacity_exhausted, deployment_not_ready, deployment_failed,
         provider_error).
      2. Match on HTTP status (401, 402, 403, 404, 409, 422, 429, 4xx, 5xx).
      3. Fall back to :class:`ParelAPIError`.
    """

    envelope: Mapping[str, Any] | None = None
    if isinstance(body, Mapping) and isinstance(body.get("error"), Mapping):
        envelope = body["error"]

    message: str
    if envelope and isinstance(envelope.get("message"), str):
        message = envelope["message"]
    elif isinstance(body, str) and body:
        message = body
    else:
        message = f"HTTP {status}"

    code = envelope.get("code") if envelope and isinstance(envelope.get("code"), str) else None
    type_ = envelope.get("type") if envelope and isinstance(envelope.get("type"), str) else None
    param = envelope.get("param") if envelope and isinstance(envelope.get("param"), str) else None

    request_id: str | None = None
    if envelope and isinstance(envelope.get("request_id"), str):
        request_id = envelope["request_id"]
    elif headers is not None:
        for candidate in ("x-request-id", "X-Request-Id", "X-Request-ID"):
            val = headers.get(candidate)
            if val:
                request_id = val
                break

    opts: dict[str, Any] = {
        "code": code,
        "type": type_,
        "status": status,
        "param": param,
        "request_id": request_id,
        "raw": body,
    }

    if code == "task_not_cancellable":
        return ParelTaskNotCancellableError(message, **opts)
    if code == "pii_blocked":
        return ParelPiiBlockedError(message, **opts)
    if code == "capacity_exhausted":
        return ParelCapacityExhaustedError(message, **opts)
    if code == "deployment_not_ready":
        return ParelDeploymentNotReadyError(message, **opts)
    if code == "deployment_failed":
        return ParelDeploymentFailedError(message, **opts)
    if code == "provider_error":
        return ParelProviderError(message, **opts)

    if status == 401:
        return ParelAuthenticationError(message, **opts)
    if status == 402:
        return ParelBudgetExceededError(message, **opts)
    if status == 403:
        return ParelPermissionError(message, **opts)
    if status == 404:
        return ParelNotFoundError(message, **opts)
    if status == 409:
        return ParelConflictError(message, **opts)
    if status == 422:
        return ParelValidationError(message, **opts)
    if status == 429:
        if headers is not None:
            retry_header = headers.get("retry-after") or headers.get("Retry-After")
            if retry_header:
                try:
                    opts["retry_after"] = float(retry_header)
                except (TypeError, ValueError):
                    pass
        return ParelRateLimitError(message, **opts)
    if 400 <= status < 500:
        return ParelValidationError(message, **opts)
    if status >= 500:
        return ParelServerError(message, **opts)
    return ParelAPIError(message, **opts)


__all__ = [
    "ParelError",
    "ParelAPIError",
    "ParelConfigError",
    "ParelTimeoutError",
    "ParelConnectionError",
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
