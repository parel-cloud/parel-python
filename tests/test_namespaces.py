"""Namespace method smoke tests. Uses ``httpx.MockTransport`` to assert the
SDK talks to the right paths with the right shapes.
"""

from __future__ import annotations

import httpx
import pytest

from parel_cloud import AsyncParel, Parel, ParelTaskNotCancellableError


def _sync_parel(handler) -> Parel:
    transport = httpx.MockTransport(handler)
    parel = Parel(api_key="k", base_url="https://api.parel.test")
    parel.http._client.close()
    parel.http._client = httpx.Client(
        base_url=parel.base_url, transport=transport, timeout=httpx.Timeout(5.0)
    )
    return parel


def _async_parel(handler) -> AsyncParel:
    transport = httpx.MockTransport(handler)
    parel = AsyncParel(api_key="k", base_url="https://api.parel.test")
    # Replace the live client with a mocked transport.
    parel.http._client = httpx.AsyncClient(
        base_url=parel.base_url, transport=transport, timeout=httpx.Timeout(5.0)
    )
    return parel


def test_credits_get() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/usage/budget"
        return httpx.Response(
            200, json={"tenant_id": "t", "limit_usd": 10.0, "spent_usd": 3.0, "remaining_usd": 7.0}
        )

    parel = _sync_parel(handler)
    try:
        snap = parel.credits.get()
        assert snap["remaining_usd"] == 7.0
    finally:
        parel.close()


def test_models_list_and_retrieve() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"object": "list", "data": [{"id": "m1"}]})
        if request.url.path == "/v1/models/gpt-4":
            return httpx.Response(200, json={"id": "gpt-4"})
        return httpx.Response(404, json={"error": {"message": "nope"}})

    parel = _sync_parel(handler)
    try:
        assert parel.models.list()["data"] == [{"id": "m1"}]
        assert parel.models.retrieve("gpt-4")["id"] == "gpt-4"
    finally:
        parel.close()


def test_tasks_get_and_cancel_conflict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/tasks/abc":
            return httpx.Response(200, json={"task_id": "abc", "status": "completed"})
        if request.url.path == "/v1/tasks/abc/cancel":
            return httpx.Response(
                409,
                json={"error": {"message": "already done", "code": "task_not_cancellable"}},
            )
        return httpx.Response(404, json={"error": {"message": "nope"}})

    parel = _sync_parel(handler)
    try:
        assert parel.tasks.get("abc")["status"] == "completed"
        with pytest.raises(ParelTaskNotCancellableError):
            parel.tasks.cancel("abc")
    finally:
        parel.close()


def test_tasks_wait_for_polls_until_terminal() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        status = "completed" if calls["n"] >= 3 else "processing"
        return httpx.Response(200, json={"task_id": "t1", "status": status})

    parel = _sync_parel(handler)
    try:
        task = parel.tasks.wait_for("t1", timeout_s=2.0, interval_s=0.01)
        assert task["status"] == "completed"
        assert calls["n"] == 3
    finally:
        parel.close()


def test_images_generate_polls_task_submission() -> None:
    state = {"submitted": False, "polls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/images/generations":
            state["submitted"] = True
            return httpx.Response(200, json={"task_id": "img-1", "poll_url": "/v1/tasks/img-1"})
        if request.url.path == "/v1/tasks/img-1":
            state["polls"] += 1
            status = "completed" if state["polls"] >= 2 else "processing"
            return httpx.Response(
                200, json={"task_id": "img-1", "status": status, "result": {"url": "x"}}
            )
        return httpx.Response(404, json={"error": {"message": "nope"}})

    parel = _sync_parel(handler)
    try:
        task = parel.images.generate(
            model="flux-schnell", prompt="a dog", timeout_s=2.0, interval_s=0.01
        )
        assert task["status"] == "completed"
        assert state["submitted"]
        assert state["polls"] >= 2
    finally:
        parel.close()


def test_images_generate_wait_false_returns_submission() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"task_id": "img-2", "poll_url": "/v1/tasks/img-2"})

    parel = _sync_parel(handler)
    try:
        submission = parel.images.generate(
            model="flux-schnell", prompt="a cat", wait=False
        )
        assert submission["task_id"] == "img-2"
    finally:
        parel.close()


def test_images_generate_sync_response_bypasses_polling() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Provider returned image data inline (no task handle).
        return httpx.Response(
            200, json={"data": [{"url": "https://cdn/x.png"}], "created": 1}
        )

    parel = _sync_parel(handler)
    try:
        result = parel.images.generate(model="flux-schnell", prompt="a horse")
        assert "data" in result
    finally:
        parel.close()


def test_gpu_list_unwraps_deployments_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"deployments": [{"id": "d1", "status": "running"}]}
        )

    parel = _sync_parel(handler)
    try:
        deps = parel.gpu.list()
        assert deps == [{"id": "d1", "status": "running"}]
    finally:
        parel.close()


def test_gpu_chat_posts_to_deployment_route() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/deployments/dep_1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})

    parel = _sync_parel(handler)
    try:
        resp = parel.gpu.chat("dep_1", {"messages": [{"role": "user", "content": "hi"}]})
        assert resp["choices"][0]["message"]["content"] == "hi"
    finally:
        parel.close()


def test_gpu_wait_for_running_polls() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        status = "running" if calls["n"] >= 3 else "creating"
        return httpx.Response(200, json={"id": "dep_1", "status": status})

    parel = _sync_parel(handler)
    try:
        dep = parel.gpu.wait_for_running("dep_1", timeout_s=2.0, interval_s=0.01)
        assert dep["status"] == "running"
    finally:
        parel.close()


def test_compare_run_submits_then_polls() -> None:
    state = {"got_post": False, "gets": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/compare/runs":
            state["got_post"] = True
            return httpx.Response(200, json={"id": "run_1", "status": "queued"})
        if request.method == "GET" and request.url.path == "/v1/compare/runs/run_1":
            state["gets"] += 1
            status = "completed" if state["gets"] >= 2 else "running"
            return httpx.Response(200, json={"id": "run_1", "status": status})
        return httpx.Response(404, json={"error": {"message": "x"}})

    parel = _sync_parel(handler)
    try:
        run = parel.compare.run(
            models=["m1", "m2"], prompt="x", timeout_s=2.0, interval_s=0.01
        )
        assert run["status"] == "completed"
        assert state["got_post"]
    finally:
        parel.close()


def test_compare_list_runs_unwraps_runs_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"runs": [{"id": "r1"}, {"id": "r2"}]})

    parel = _sync_parel(handler)
    try:
        runs = parel.compare.list_runs()
        assert len(runs) == 2
    finally:
        parel.close()


def test_audio_transcribe_posts_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/audio/transcriptions"
        return httpx.Response(200, json={"text": "hello world"})

    parel = _sync_parel(handler)
    try:
        result = parel.audio.transcribe(file="base64...", model="whisper-v3")
        assert result["text"] == "hello world"
    finally:
        parel.close()


async def test_async_credits_get() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"tenant_id": "t", "limit_usd": 1.0, "spent_usd": 0.0, "remaining_usd": 1.0})

    parel = _async_parel(handler)
    try:
        snap = await parel.credits.get()
        assert snap["remaining_usd"] == 1.0
    finally:
        await parel.aclose()


async def test_async_images_generate_polls() -> None:
    state = {"polls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/images/generations":
            return httpx.Response(200, json={"task_id": "img-a"})
        if request.url.path == "/v1/tasks/img-a":
            state["polls"] += 1
            status = "completed" if state["polls"] >= 2 else "processing"
            return httpx.Response(200, json={"task_id": "img-a", "status": status})
        return httpx.Response(404, json={"error": {"message": "x"}})

    parel = _async_parel(handler)
    try:
        task = await parel.images.generate(
            model="flux-schnell", prompt="x", timeout_s=2.0, interval_s=0.01
        )
        assert task["status"] == "completed"
    finally:
        await parel.aclose()
