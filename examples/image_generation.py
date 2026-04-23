"""Submit an image generation and wait for the result.

The SDK submits to ``/v1/images/generations`` and polls the task until
terminal under the hood; callers get a synchronous return. Pass
``wait=False`` for a fire-and-forget submission.
"""

from __future__ import annotations

import os

from parel_cloud import Parel


def main() -> None:
    parel = Parel(api_key=os.environ["PAREL_API_KEY"])

    task = parel.images.generate(
        model="flux-schnell",
        prompt="a cozy cabin in a snowy forest at dusk, photoreal",
        n=1,
        size="1024x1024",
        timeout_s=180.0,
        on_tick=lambda t: print(f"  status={t.get('status')} progress={t.get('progress')}"),
    )

    print("final task:", task.get("status"))
    result = task.get("result") or {}
    for entry in result.get("data", []):
        print("  url:", entry.get("url"))


if __name__ == "__main__":
    main()
