"""BYOM: deploy a HuggingFace model, chat against it, and tear it down.

Warning: running this example provisions a real GPU pod. Make sure to let
the ``finally`` block run so the deployment is deleted.
"""

from __future__ import annotations

import os

from parel_cloud import Parel, ParelCapacityExhaustedError


def main() -> None:
    parel = Parel(api_key=os.environ["PAREL_API_KEY"])
    huggingface_id = "meta-llama/Llama-3.1-8B-Instruct"

    info = parel.gpu.validate_huggingface(huggingface_id)
    print(f"recommended tier: {info.get('recommended_gpu_tier')}")

    try:
        dep = parel.gpu.create(
            huggingface_id=huggingface_id,
            gpu_tier=info.get("recommended_gpu_tier") or "rtx4090",
            idle_timeout_minutes=10,
            budget_limit_usd=1.0,
        )
    except ParelCapacityExhaustedError:
        print("no GPU capacity right now — try again later")
        return

    deployment_id = dep["id"]
    try:
        print(f"provisioning {deployment_id}, waiting for running…")
        running = parel.gpu.wait_for_running(
            deployment_id,
            on_tick=lambda d: print(f"  {d.get('status')}"),
        )
        print(f"ready: {running.get('status')}")

        resp = parel.gpu.chat(
            deployment_id,
            {"messages": [{"role": "user", "content": "say hi in three words"}]},
        )
        print("reply:", resp["choices"][0]["message"]["content"])
    finally:
        print("tearing down…")
        parel.gpu.delete(deployment_id)


if __name__ == "__main__":
    main()
