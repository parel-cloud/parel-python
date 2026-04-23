"""Shared type definitions used across namespaces.

Mirrors the gateway's Pydantic schemas (``gateway/app/schemas.py``) without
pulling in a runtime validator. The SDK trusts the server envelope and
exposes :class:`TypedDict` shapes so callers still get IDE autocompletion.

All TypedDicts declare ``total=False`` where the gateway may omit fields
(legacy rows, optional telemetry, forward-compat extras).
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

TaskStatus = Literal["pending", "processing", "completed", "failed", "cancelled"]
TaskType = Literal["image", "video", "tts", "music", "stt"]


class TaskError(TypedDict, total=False):
    message: str
    type: str
    code: str


class Task(TypedDict, total=False):
    task_id: str
    status: TaskStatus
    task_type: str
    model: str
    progress: float
    created_at: str | None
    started_at: str
    completed_at: str
    result: dict[str, Any] | None
    error: TaskError


class TaskCancelResult(TypedDict, total=False):
    task_id: str
    status: Literal["cancelled"]
    refunded_at: str
    refund_amount_usd: float


class BudgetSnapshot(TypedDict, total=False):
    tenant_id: str
    limit_usd: float
    spent_usd: float
    remaining_usd: float
    updated_at: str
    version: int


class ModelInfo(TypedDict, total=False):
    id: str
    display_name: str
    model_type: str
    provider: str
    badges: list[str]
    capabilities: list[str]
    pricing: dict[str, Any]
    status: str


class ModelListResponse(TypedDict, total=False):
    object: Literal["list"]
    data: list[ModelInfo]


DeploymentStatus = Literal[
    "queued",
    "creating",
    "starting",
    "running",
    "stopping",
    "stopped",
    "sleeping",
    "error",
]


class Deployment(TypedDict, total=False):
    id: str
    name: str
    huggingface_id: str
    gpu_tier: str
    provider: str
    status: str
    hourly_cost: float
    budget_limit_usd: float
    budget_spent_usd: float
    idle_timeout_minutes: int
    parel_model_id: str
    created_at: str
    started_at: str
    last_request_at: str
    error_code: str
    error_message: str


class GpuTier(TypedDict, total=False):
    id: str
    gpu_name: str
    vram_gb: float
    price_per_hour_usd: float
    provider: str
    available: bool


class CompareRun(TypedDict, total=False):
    id: str
    status: str
    prompt: str
    models: list[str]
    created_at: str
    completed_at: str
    results: dict[str, Any]


class HfValidateResponse(TypedDict, total=False):
    valid: bool
    model_id: str
    architecture: str
    tgi_compatible: bool
    vllm_compatible: bool
    vram_fp16_gb: float
    vram_int4_gb: float
    recommended_gpu_tier: str
    needs_new_vllm: bool
    provider_compat_hint: str


class PrefetchStatus(TypedDict, total=False):
    status: str
    progress: float
    size_bytes: int


class TaskSubmission(TypedDict, total=False):
    task_id: str
    poll_url: str


__all__ = [
    "TaskStatus",
    "TaskType",
    "TaskError",
    "Task",
    "TaskCancelResult",
    "BudgetSnapshot",
    "ModelInfo",
    "ModelListResponse",
    "Deployment",
    "DeploymentStatus",
    "GpuTier",
    "CompareRun",
    "HfValidateResponse",
    "PrefetchStatus",
    "TaskSubmission",
]
