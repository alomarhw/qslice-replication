"""Best-effort fetcher for QASMBench small OpenQASM corpus.

The script clones https://github.com/pnnl/QASMBench into data/qasmbench/small when possible and writes
data/fetch_manifest.json. It exits 0 even on network/git failures; main.py enforces strict data policy.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

RANDOM_SEED = int(os.environ.get("RP_RANDOM_SEED", 42))

DATA_ROOT = Path("data")
TARGET = DATA_ROOT / "qasmbench" / "small"
URL = "https://github.com/pnnl/QASMBench"
DATASET_NAME = "QASMBench (small)"


def sha256_for_files(paths: list[Path], limit: int = 64) -> str:
    h = hashlib.sha256()
    for p in sorted(paths)[:limit]:
        try:
            h.update(str(p.relative_to(DATA_ROOT)).encode("utf-8"))
            h.update(p.read_bytes()[:1024 * 1024])
        except Exception:
            continue
    return h.hexdigest()


def write_manifest(ok: list[dict[str, Any]], failed: list[dict[str, Any]]) -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = {"ok": ok, "failed": failed}
    with (DATA_ROOT / "fetch_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, allow_nan=False)


def main() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    ok: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    try:
        existing = list(DATA_ROOT.rglob("*.qasm"))
        if existing:
            checksum = sha256_for_files(existing)
            ok.append(
                {
                    "path": str(DATA_ROOT),
                    "recordCount": len(existing),
                    "checksum": checksum,
                    "version": "",
                    "license": "",
                    "citation": "QASMBench OpenQASM benchmark corpus",
                    "columns": [],
                    "contract": {"datasetName": DATASET_NAME, "url": URL},
                }
            )
            print(f"Existing QASM corpus detected: {len(existing)} .qasm files under {DATA_ROOT}")
            write_manifest(ok, failed)
            return

        if shutil.which("git") is None:
            raise RuntimeError("git executable not found; cannot clone repository")

        TARGET.parent.mkdir(parents=True, exist_ok=True)
        if not TARGET.exists():
            print(f"Cloning {URL} into {TARGET}")
            subprocess.run(
                ["git", "clone", "--depth", "1", URL, str(TARGET)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=180,
            )
        qasm_files = list(TARGET.rglob("*.qasm"))
        checksum = sha256_for_files(qasm_files)
        ok.append(
            {
                "path": str(TARGET),
                "recordCount": len(qasm_files),
                "checksum": checksum,
                "version": "",
                "license": "",
                "citation": "QASMBench OpenQASM benchmark corpus",
                "columns": [],
                "contract": {"datasetName": DATASET_NAME, "url": URL},
            }
        )
        print(f"Saved {len(qasm_files)} .qasm files to {TARGET}")
    except Exception as exc:
        warning = f"WARNING: QASMBench fetch failed: {exc}"
        print(warning)
        failed.append({"datasetName": DATASET_NAME, "url": URL, "error": str(exc)})
    finally:
        write_manifest(ok, failed)


if __name__ == "__main__":
    main()