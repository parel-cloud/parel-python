# Parel SDK for Python

Official Python SDK for [Parel](https://parel.cloud). 100+ AI models, GPU rental (BYOM), compare, and credits via a single OpenAI-compatible API.

> Feature parity with [@parel-cloud/node](https://github.com/parel-cloud/parel-node) (v0.1.1). Both SDKs wrap the same gateway and share a machine-readable `parity.json`.

## Install

```bash
pip install parel-cloud
# Optional: enable the `parel.openai` lazy client (streaming, tools, vision)
pip install "parel-cloud[openai]"
```

Requires Python 3.10+.

## Quick start (sync)

```python
import os
from parel_cloud import Parel

parel = Parel(api_key=os.environ["PAREL_API_KEY"])

snapshot = parel.credits.get()
print(f"remaining: ${snapshot['remaining_usd']:.2f}")

# Drop-in OpenAI client pointed at Parel
chat = parel.openai.chat.completions.create(
    model="qwen3.5-72b",
    messages=[{"role": "user", "content": "merhaba"}],
)
print(chat.choices[0].message.content)
```

## Quick start (async)

```python
import asyncio
from parel_cloud import AsyncParel

async def main():
    async with AsyncParel() as parel:
        models = await parel.models.list()
        print(len(models["data"]))

asyncio.run(main())
```

## Namespaces

| Namespace | Purpose | Example |
| --- | --- | --- |
| `credits` | Budget snapshot | `parel.credits.get()` |
| `models` | Catalogue + metadata | `parel.models.list()` / `parel.models.retrieve("qwen3.5-72b")` |
| `tasks` | Async task polling + cancel | `parel.tasks.wait_for(task_id)` / `parel.tasks.cancel(task_id)` |
| `images` | Image generation + edit | `parel.images.generate(model="flux-schnell", prompt="...")` |
| `videos` | Video generation | `parel.videos.generate(model="seedance-1.5", prompt="...")` |
| `audio` | TTS, STT, music | `parel.audio.speech(model="...", input="...")` |
| `gpu` | BYOM deployments, HF validate, prefetch, metrics | `parel.gpu.create(huggingface_id=..., gpu_tier=...)` |
| `compare` | Multi-model head-to-head runs + conversations | `parel.compare.run(models=[...], prompt="...")` |
| `openai` | Lazy `openai.OpenAI` / `openai.AsyncOpenAI` pointed at Parel | `parel.openai.chat.completions.create(...)` |

## Typed error handling

```python
from parel_cloud import (
    Parel,
    ParelBudgetExceededError,
    ParelRateLimitError,
    ParelTaskNotCancellableError,
    ParelCapacityExhaustedError,
)

parel = Parel()

try:
    parel.images.generate(model="flux-schnell", prompt="a cat")
except ParelBudgetExceededError as err:
    print(f"top up: {err.message} (request_id={err.request_id})")
except ParelRateLimitError as err:
    print(f"slow down for {err.retry_after} seconds")
except ParelCapacityExhaustedError:
    print("no GPU capacity right now")
except ParelTaskNotCancellableError:
    print("task already terminal, nothing to cancel")
```

Every error subclasses `ParelError` and carries `message`, `code`, `status`, `request_id`, and `param`.

## BYOM (bring-your-own-model) example

```python
from parel_cloud import Parel

parel = Parel()

# 1. Validate a HuggingFace model (VRAM needs, recommended tier)
info = parel.gpu.validate_huggingface("meta-llama/Llama-3.1-8B-Instruct")
print(info["recommended_gpu_tier"])

# 2. Deploy
dep = parel.gpu.create(
    huggingface_id="meta-llama/Llama-3.1-8B-Instruct",
    gpu_tier="rtx4090",
    idle_timeout_minutes=15,
)

# 3. Wait for it to come online
running = parel.gpu.wait_for_running(dep["id"])

# 4. Inference
resp = parel.gpu.chat(dep["id"], {
    "messages": [{"role": "user", "content": "hi"}],
})
print(resp["choices"][0]["message"]["content"])

# 5. Tear down when done
parel.gpu.delete(dep["id"])
```

## Configuration

| Arg | Env var | Default |
| --- | --- | --- |
| `api_key` | `PAREL_API_KEY` | required |
| `base_url` | `PAREL_BASE_URL` | `https://api.parel.cloud` |
| `timeout_s` | — | 60 |
| `max_retries` | — | 2 (idempotent verbs only) |
| `user_agent` | — | `parel-cloud/<ver> python/<ver>` |

## Retries

`GET`, `HEAD`, `OPTIONS`, `PUT`, `DELETE` are retried on 429, 5xx, and transport errors with jittered exponential backoff (500ms base, capped at 8s). `POST` and `PATCH` are not auto-retried (the gateway considers them non-idempotent at v0.1).

## JavaScript / TypeScript

Same SDK shape, different language: [@parel-cloud/node](https://github.com/parel-cloud/parel-node).

## Roadmap

- LangChain, LlamaIndex, CrewAI, DSPy integrations (as separate packages)
- `Idempotency-Key` support for retryable POSTs
- SSE streaming helpers for long-running generations
- Multipart file upload for `audio.transcribe`

## License

MIT © [Aleonis Teknoloji](https://parel.cloud)
