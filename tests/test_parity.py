"""Validate that every method listed in ``parity.json`` is present on the
Python SDK. Both ``@parel-cloud/node`` and ``parel-cloud`` (Python) read
from the same source of truth, so drift in either SDK fails this test.
"""

from __future__ import annotations

import json
from pathlib import Path

from parel_cloud import Parel

_PARITY_PATH = Path(__file__).resolve().parent.parent / "parity.json"


def test_parity_file_exists() -> None:
    assert _PARITY_PATH.exists(), f"parity.json missing at {_PARITY_PATH}"


def test_every_listed_namespace_and_method_is_attached() -> None:
    spec = json.loads(_PARITY_PATH.read_text())
    namespaces = spec["namespaces"]

    parel = Parel(api_key="k")
    try:
        for ns_name, methods in namespaces.items():
            assert hasattr(parel, ns_name), f"Parel missing namespace {ns_name}"
            namespace = getattr(parel, ns_name)
            for method in methods:
                assert hasattr(namespace, method), (
                    f"parel.{ns_name} is missing method `{method}` "
                    f"(listed in parity.json)"
                )
                assert callable(getattr(namespace, method)), (
                    f"parel.{ns_name}.{method} is not callable"
                )
    finally:
        parel.close()
