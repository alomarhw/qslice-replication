"""OpenQASM corpus loader for the QPDG slicing experiments.

Requirements targeted:
- numpy==1.26.4
- pandas==3.0.3
- qiskit==2.4.2
- qiskit-aer==0.17.2
"""

from __future__ import annotations

import gzip
import math
import os
import random
import re
import shutil
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

RANDOM_SEED = int(os.environ.get("RP_RANDOM_SEED", 42))
random.seed(RANDOM_SEED)


@dataclass(frozen=True)
class Operation:
    index: int
    name: str
    qubits: tuple[int, ...]
    params: tuple[float, ...] = ()


@dataclass
class SimpleCircuit:
    name: str
    path: str
    num_qubits: int
    ops: list[Operation]
    source: str = ""


SUPPORTED_GATES = {
    "id", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "p", "u1", "u2", "u3", "u",
    "cx", "cnot", "cz", "cy", "ch", "swap", "ccx", "toffoli",
}


def extract_archives_in_place(data_root: Path) -> None:
    data_root.mkdir(parents=True, exist_ok=True)
    for archive in list(data_root.rglob("*")):
        if not archive.is_file():
            continue
        lower = archive.name.lower()
        try:
            if lower.endswith(".zip"):
                out = archive.with_suffix("")
                marker = out / ".extracted"
                if marker.exists():
                    continue
                out.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(archive) as zf:
                    zf.extractall(out)
                marker.write_text("ok\n", encoding="utf-8")
                print(f"Extracted archive {archive} -> {out}")
            elif lower.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2")):
                out = archive.with_suffix("").with_suffix("")
                marker = out / ".extracted"
                if marker.exists():
                    continue
                out.mkdir(parents=True, exist_ok=True)
                with tarfile.open(archive) as tf:
                    tf.extractall(out)
                marker.write_text("ok\n", encoding="utf-8")
                print(f"Extracted archive {archive} -> {out}")
            elif lower.endswith(".qasm.gz"):
                out = archive.with_suffix("")
                if out.exists():
                    continue
                with gzip.open(archive, "rb") as src, out.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                print(f"Decompressed {archive} -> {out}")
        except Exception as exc:
            print(f"WARNING: could not extract {archive}: {exc}")


def _clean_lines(text: str) -> Iterable[str]:
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        for part in line.split(";"):
            part = part.strip()
            if part:
                yield part + ";"


def _safe_eval_expr(expr: str) -> float:
    expr = expr.strip().replace("^", "**")
    allowed = {"pi": math.pi, "sin": math.sin, "cos": math.cos, "tan": math.tan, "sqrt": math.sqrt}
    return float(eval(expr, {"__builtins__": {}}, allowed))


def _parse_params(param_text: str | None) -> tuple[float, ...]:
    if not param_text:
        return ()
    pieces: list[str] = []
    current = ""
    depth = 0
    for ch in param_text:
        if ch == "," and depth == 0:
            pieces.append(current)
            current = ""
        else:
            current += ch
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
    if current:
        pieces.append(current)
    vals: list[float] = []
    for p in pieces:
        try:
            vals.append(_safe_eval_expr(p))
        except Exception:
            vals.append(0.0)
    return tuple(vals)


def parse_qasm_file(path: Path, source: str = "") -> SimpleCircuit:
    text = path.read_text(encoding="utf-8", errors="ignore")
    qreg_offsets: dict[str, int] = {}
    qreg_sizes: dict[str, int] = {}
    total_qubits = 0
    raw_ops: list[tuple[str, tuple[int, ...], tuple[float, ...]]] = []

    for line in _clean_lines(text):
        qreg_match = re.match(r"qreg\s+([A-Za-z_]\w*)\[(\d+)\]\s*;", line)
        if qreg_match:
            name, size_s = qreg_match.group(1), qreg_match.group(2)
            qreg_offsets[name] = total_qubits
            qreg_sizes[name] = int(size_s)
            total_qubits += int(size_s)
            continue

        if line.startswith(("OPENQASM", "include", "creg", "barrier", "measure", "reset", "gate ", "opaque ")):
            continue

        m = re.match(r"([A-Za-z_]\w*)\s*(?:\((.*?)\))?\s+(.+?)\s*;", line)
        if not m:
            continue
        gate = m.group(1).lower()
        if gate not in SUPPORTED_GATES:
            continue
        params = _parse_params(m.group(2))
        args = [a.strip() for a in m.group(3).split(",")]
        qubits: list[int] = []
        for arg in args:
            qm = re.match(r"([A-Za-z_]\w*)\[(\d+)\]", arg)
            if not qm:
                continue
            reg, idx_s = qm.group(1), qm.group(2)
            if reg in qreg_offsets:
                qubits.append(qreg_offsets[reg] + int(idx_s))
        if qubits:
            raw_ops.append((gate, tuple(qubits), params))

    ops = [Operation(i, name, qs, params) for i, (name, qs, params) in enumerate(raw_ops)]
    return SimpleCircuit(name=path.stem, path=str(path), num_qubits=total_qubits, ops=ops, source=source)


# Curated per-corpus subdirectories (relative to the data root) and their display labels.
CORPUS_DIRS = {
    "qasmbench": "QASMBench",
    "mqtbench": "MQT Bench",
    "veriqbench": "VeriQBench",
}


def load_corpora(
    data_root: Path,
    max_per_corpus: int,
    max_qubits: int,
    max_ops: int,
    min_total: int = 1,
) -> list[SimpleCircuit]:
    """Load circuits from the three curated benchmark subdirectories, tagging each by source corpus.

    Scans ``data_root/{qasmbench,mqtbench,veriqbench}`` (skipping the noisy extracted-archive trees),
    keeps circuits within the simulation caps, and takes up to ``max_per_corpus`` from each corpus
    (smallest-first for tractable exact simulation). Falls back to a flat recursive scan of
    ``data_root`` (legacy single-corpus behaviour) when none of the curated subdirs exist.
    """
    extract_archives_in_place(data_root)
    have_curated = any((data_root / sub).is_dir() for sub in CORPUS_DIRS)
    if not have_curated:
        return load_qasm_corpus(data_root, max_per_corpus, max_qubits, max_ops, min_circuits=min_total)

    combined: list[SimpleCircuit] = []
    summary: dict[str, int] = {}
    for sub, label in CORPUS_DIRS.items():
        cdir = data_root / sub
        if not cdir.is_dir():
            continue
        files = sorted(cdir.rglob("*.qasm"), key=lambda p: str(p))
        parsed: list[SimpleCircuit] = []
        for p in files:
            try:
                c = parse_qasm_file(p, source=label)
            except Exception:
                continue
            if c.num_qubits <= 0 or not c.ops:
                continue
            if c.num_qubits > max_qubits or len(c.ops) > max_ops:
                continue
            parsed.append(c)
        # Smallest-first so exact statevector simulation stays tractable, then take the cap.
        parsed.sort(key=lambda c: (c.num_qubits, len(c.ops), c.name))
        kept = parsed[:max_per_corpus]
        summary[label] = len(kept)
        combined.extend(kept)

    if len(combined) < min_total:
        raise RuntimeError(
            f"DATA NEEDED: only {len(combined)} simulable circuits across "
            f"{list(CORPUS_DIRS.values())} within caps max_qubits={max_qubits}, max_ops={max_ops}. "
            f"Per-corpus: {summary}. Increase caps or provide more small circuits."
        )
    print(
        f"Loaded {len(combined)} in-range OpenQASM circuits across corpora {summary} "
        f"(max_qubits={max_qubits}, max_ops={max_ops}, max_per_corpus={max_per_corpus})."
    )
    return combined


def load_qasm_corpus(
    root: Path,
    max_circuits: int,
    max_qubits: int,
    max_ops: int,
    min_circuits: int = 1,
) -> list[SimpleCircuit]:
    extract_archives_in_place(root)
    files = sorted(root.rglob("*.qasm"), key=lambda p: (len(str(p)), str(p)))
    if not files:
        raise RuntimeError(
            f"DATA NEEDED: required OpenQASM corpus 'QASMBench (small)' is missing. "
            f"No .qasm files were found recursively under {root.resolve()}."
        )

    circuits: list[SimpleCircuit] = []
    parse_failures = 0
    oversized = 0
    for p in files:
        try:
            c = parse_qasm_file(p)
        except Exception:
            parse_failures += 1
            continue
        if c.num_qubits <= 0 or not c.ops:
            continue
        if c.num_qubits > max_qubits or len(c.ops) > max_ops:
            oversized += 1
            continue
        circuits.append(c)
        if len(circuits) >= max_circuits:
            break

    if len(circuits) < min_circuits:
        raise RuntimeError(
            f"DATA NEEDED: found {len(files)} .qasm files under {root.resolve()}, but only "
            f"{len(circuits)} were simulable within caps max_qubits={max_qubits}, max_ops={max_ops}. "
            f"parse_failures={parse_failures}, oversized={oversized}. Increase caps or provide small QASMBench circuits."
        )
    print(
        f"Loaded {len(circuits)} in-range OpenQASM circuits from {root} "
        f"(max_qubits={max_qubits}, max_ops={max_ops}, parse_failures={parse_failures}, oversized={oversized})."
    )
    return circuits