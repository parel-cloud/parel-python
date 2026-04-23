"""Error hierarchy + ``parse_http_error`` unit tests."""

from __future__ import annotations

from typing import Mapping

from parel_cloud import (
    ParelAPIError,
    ParelAuthenticationError,
    ParelBudgetExceededError,
    ParelCapacityExhaustedError,
    ParelConflictError,
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
    ParelValidationError,
    parse_http_error,
)


class _Headers(Mapping[str, str]):
    def __init__(self, data: dict[str, str]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> str:
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def get(self, key: str, default: str | None = None) -> str | None:  # type: ignore[override]
        return self._data.get(key, default)


def test_base_error_captures_fields() -> None:
    err = ParelError(
        "boom",
        code="x",
        type="server_error",
        status=500,
        request_id="req_1",
        param="foo",
        raw={"any": 1},
    )
    assert err.message == "boom"
    assert err.code == "x"
    assert err.status == 500
    assert err.request_id == "req_1"
    assert err.param == "foo"
    assert err.raw == {"any": 1}
    assert "status=500" in str(err)
    assert "code=x" in str(err)


def test_every_subclass_inherits_parel_error() -> None:
    subclasses = [
        ParelAPIError,
        ParelAuthenticationError,
        ParelPermissionError,
        ParelNotFoundError,
        ParelConflictError,
        ParelValidationError,
        ParelRateLimitError,
        ParelBudgetExceededError,
        ParelServerError,
        ParelTaskNotCancellableError,
        ParelPiiBlockedError,
        ParelCapacityExhaustedError,
        ParelDeploymentNotReadyError,
        ParelDeploymentFailedError,
        ParelProviderError,
    ]
    for cls in subclasses:
        instance = cls("msg")
        assert isinstance(instance, ParelError)


def test_status_to_subclass_mapping() -> None:
    body = {"error": {"message": "bad"}}
    assert isinstance(parse_http_error(401, body), ParelAuthenticationError)
    assert isinstance(parse_http_error(402, body), ParelBudgetExceededError)
    assert isinstance(parse_http_error(403, body), ParelPermissionError)
    assert isinstance(parse_http_error(404, body), ParelNotFoundError)
    assert isinstance(parse_http_error(409, body), ParelConflictError)
    assert isinstance(parse_http_error(422, body), ParelValidationError)
    assert isinstance(parse_http_error(400, body), ParelValidationError)
    assert isinstance(parse_http_error(500, body), ParelServerError)
    assert isinstance(parse_http_error(502, body), ParelServerError)


def test_code_refinement_wins_over_status() -> None:
    body = {"error": {"message": "nope", "code": "task_not_cancellable"}}
    err = parse_http_error(409, body)
    assert isinstance(err, ParelTaskNotCancellableError)
    assert isinstance(err, ParelConflictError)

    pii = parse_http_error(400, {"error": {"message": "pii", "code": "pii_blocked"}})
    assert isinstance(pii, ParelPiiBlockedError)
    assert isinstance(pii, ParelValidationError)

    cap = parse_http_error(500, {"error": {"message": "x", "code": "capacity_exhausted"}})
    assert isinstance(cap, ParelCapacityExhaustedError)
    assert isinstance(cap, ParelServerError)

    dnr = parse_http_error(409, {"error": {"message": "x", "code": "deployment_not_ready"}})
    assert isinstance(dnr, ParelDeploymentNotReadyError)

    dfl = parse_http_error(502, {"error": {"message": "x", "code": "deployment_failed"}})
    assert isinstance(dfl, ParelDeploymentFailedError)

    prov = parse_http_error(502, {"error": {"message": "x", "code": "provider_error"}})
    assert isinstance(prov, ParelProviderError)


def test_rate_limit_parses_retry_after_header() -> None:
    headers = _Headers({"retry-after": "12.5"})
    err = parse_http_error(429, {"error": {"message": "slow"}}, headers)
    assert isinstance(err, ParelRateLimitError)
    assert err.retry_after == 12.5


def test_rate_limit_without_retry_after() -> None:
    err = parse_http_error(429, {"error": {"message": "slow"}})
    assert isinstance(err, ParelRateLimitError)
    assert err.retry_after is None


def test_opaque_body_falls_back_to_generic_message() -> None:
    err = parse_http_error(418, "teapot")
    assert isinstance(err, ParelValidationError)
    assert err.message == "teapot"


def test_opaque_body_with_no_text_uses_http_status_message() -> None:
    err = parse_http_error(418, None)
    assert err.message == "HTTP 418"


def test_unrecognized_status_uses_api_error() -> None:
    err = parse_http_error(100, {"error": {"message": "weird"}})
    assert isinstance(err, ParelAPIError)
    assert err.status == 100


def test_request_id_pulled_from_envelope_first() -> None:
    body = {"error": {"message": "x", "request_id": "req_from_body"}}
    headers = _Headers({"x-request-id": "req_from_header"})
    err = parse_http_error(500, body, headers)
    assert err.request_id == "req_from_body"


def test_request_id_fallback_to_header() -> None:
    headers = _Headers({"x-request-id": "req_from_header"})
    err = parse_http_error(500, {"error": {"message": "x"}}, headers)
    assert err.request_id == "req_from_header"


def test_param_and_type_carried_through() -> None:
    body = {"error": {"message": "x", "param": "model", "type": "invalid_request_error"}}
    err = parse_http_error(422, body)
    assert err.param == "model"
    assert err.type == "invalid_request_error"


def test_raw_body_preserved() -> None:
    body = {"error": {"message": "x"}, "trace_id": "abc"}
    err = parse_http_error(500, body)
    assert err.raw == body


def test_capacity_exhausted_defaults_status_when_missing_in_code_path() -> None:
    err = parse_http_error(500, {"error": {"message": "x", "code": "capacity_exhausted"}})
    assert err.status == 500
    assert err.code == "capacity_exhausted"


def test_budget_exceeded_at_402_without_code() -> None:
    err = parse_http_error(402, {"error": {"message": "broke"}})
    assert isinstance(err, ParelBudgetExceededError)
