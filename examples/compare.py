"""Run a quick head-to-head compare across multiple models.

The SDK submits the run, then polls until terminal. Set ``wait=False`` to
return the initial run handle immediately.
"""

from __future__ import annotations

import os

from parel_cloud import Parel


def main() -> None:
    parel = Parel(api_key=os.environ["PAREL_API_KEY"])

    run = parel.compare.run(
        models=["qwen3.5-72b", "gpt-4o-mini", "gemini-2.0-flash"],
        prompt="Bana 2 cümlelik bir dedektif romanı açılışı yaz.",
        name="noir-intro",
        timeout_s=300.0,
    )

    print("status:", run.get("status"))
    for lane_id, lane in (run.get("results") or {}).items():
        print(f"\n--- {lane_id} ---")
        print(lane)


if __name__ == "__main__":
    main()
