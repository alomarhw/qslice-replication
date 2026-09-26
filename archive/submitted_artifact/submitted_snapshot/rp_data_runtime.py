"""the toolkit data-manifest helpers.

This module intentionally exposes exactly two helpers:
resolve_data_path(key, data_root="data", required=True) and load_manifest(data_root="data").
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RANDOM_SEED = int(__import__("os").environ.get("RP_RANDOM_SEED", 42))


def load_manifest(data_root: str = "data") -> dict[str, list[dict[str, Any]]]:
    manifest_path = Path(data_root) / "fetch_manifest.json"
    if not manifest_path.exists():
        return {"ok": [], "failed": []}
    with manifest_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {"ok": list(data.get("ok", [])), "failed": list(data.get("failed", []))}


def resolve_data_path(key: str, data_root: str = "data", required: bool = True) -> Path:
    manifest = load_manifest(data_root)
    key_l = key.lower()
    matches: list[Path] = []
    available: list[str] = []
    for entry in manifest.get("ok", []):
        contract = entry.get("contract", {}) or {}
        names = [
            str(contract.get("datasetName", "")),
            str(contract.get("name", "")),
            str(entry.get("datasetName", "")),
            str(entry.get("name", "")),
            str(entry.get("path", "")),
        ]
        available.extend([n for n in names if n])
        if any(key_l in n.lower() or n.lower() in key_l for n in names if n):
            p = Path(entry.get("path", ""))
            if not p.is_absolute():
                p = Path(data_root).parent / p
            matches.append(p)
    if matches:
        return matches[0]
    if required:
        listed = sorted(set(available)) or ["<none in data/fetch_manifest.json>"]
        raise RuntimeError(
            f"Required dataset '{key}' was not found in {Path(data_root) / 'fetch_manifest.json'}. "
            f"Available manifest datasets/paths: {listed}"
        )
    return Path(data_root)