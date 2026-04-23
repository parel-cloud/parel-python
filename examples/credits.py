"""Read the current budget snapshot."""

from __future__ import annotations

import os

from parel_cloud import Parel


def main() -> None:
    parel = Parel(api_key=os.environ["PAREL_API_KEY"])
    snap = parel.credits.get()
    print(
        f"limit=${snap['limit_usd']:.2f}  "
        f"spent=${snap['spent_usd']:.2f}  "
        f"remaining=${snap['remaining_usd']:.2f}"
    )


if __name__ == "__main__":
    main()
