"""Quickstart: list models, check budget, stream a chat completion via OpenAI.

Run::

    export PAREL_API_KEY="pk-..."
    pip install "parel-cloud[openai]"
    python examples/quickstart.py
"""

from __future__ import annotations

import os

from parel_cloud import Parel


def main() -> None:
    parel = Parel(api_key=os.environ["PAREL_API_KEY"])

    snapshot = parel.credits.get()
    print(f"remaining: ${snapshot['remaining_usd']:.2f} of ${snapshot['limit_usd']:.2f}")

    models = parel.models.list()
    print(f"catalogue: {len(models.get('data', []))} models")

    chat = parel.openai.chat.completions.create(
        model="qwen3.5-72b",
        messages=[{"role": "user", "content": "Merhaba, seni tanıyabilir miyim?"}],
        max_tokens=200,
    )
    print("\n---")
    print(chat.choices[0].message.content)


if __name__ == "__main__":
    main()
