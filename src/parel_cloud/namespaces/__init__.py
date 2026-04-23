"""Parel SDK namespaces — sync + async mirrors of the gateway API surface."""

from .compare import AsyncCompareNamespace, CompareNamespace
from .credits import AsyncCreditsNamespace, CreditsNamespace
from .generations import (
    AsyncAudioNamespace,
    AsyncImagesNamespace,
    AsyncVideosNamespace,
    AudioNamespace,
    ImagesNamespace,
    VideosNamespace,
)
from .gpu import AsyncGpuNamespace, GpuNamespace
from .models import AsyncModelsNamespace, ModelsNamespace
from .tasks import AsyncTasksNamespace, TasksNamespace

__all__ = [
    "CompareNamespace",
    "AsyncCompareNamespace",
    "CreditsNamespace",
    "AsyncCreditsNamespace",
    "AudioNamespace",
    "AsyncAudioNamespace",
    "ImagesNamespace",
    "AsyncImagesNamespace",
    "VideosNamespace",
    "AsyncVideosNamespace",
    "GpuNamespace",
    "AsyncGpuNamespace",
    "ModelsNamespace",
    "AsyncModelsNamespace",
    "TasksNamespace",
    "AsyncTasksNamespace",
]
