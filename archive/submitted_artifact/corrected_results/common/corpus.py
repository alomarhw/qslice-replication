"""Corpus selection and circuit preparation shared by both re-runs (fixed in PROTOCOL.md).

Corpus A: the 161 circuits of the paper's RQ1-RQ3, selected by the unchanged evaluation loader
(`load_corpora`, max 14 qubits, max 220 ops, 80 per corpus, smallest first). Only the file list is
taken from it. Each file is then loaded as written with qiskit (`qasm2.load`, legacy custom
instructions), so mid-circuit measurement, reset and classical feedback are kept.

Corpus B (ablation only): every VeriQBench `dynamic/` circuit with <= 14 qubits and <= 220
instructions after preparation, and not already in corpus A.

Preparation, applied identically to every circuit before any slicer sees it:
  1. drop barriers;
  2. drop terminal measurements (no later instruction on the qubit, and the classical bit is never
     read by a later condition), because the soundness criterion is the criterion qubit's reduced
     state before readout;
  3. decompose gates acting on more than 8 qubits into their definitions (repeat until none remain),
     as the method prototype does, so exact simulation stays tractable.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from qiskit import QuantumCircuit, qasm2

from common.oracle import terminal_measurements

MAX_QUBITS, MAX_OPS, PER_CORPUS, FLATTEN_ARITY = 14, 220, 80, 8


@dataclass
class Entry:
    corpus: str
    name: str
    path: str               # relative to the data root
    qc: Optional[QuantumCircuit]
    error: str = ""


def prepare(qc: QuantumCircuit) -> QuantumCircuit:
    term = terminal_measurements(qc)
    out = qc.copy_empty_like()
    for k, inst in enumerate(qc.data):
        if inst.operation.name == "barrier" or k in term:
            continue
        out.append(inst)
    for _ in range(16):
        wide = sorted({i.operation.name for i in out.data
                       if i.operation.num_qubits > FLATTEN_ARITY and i.operation.name != "if_else"})
        if not wide:
            break
        out = out.decompose(gates_to_decompose=wide)
    return out


def load(path: Path) -> QuantumCircuit:
    return prepare(qasm2.load(str(path), custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS))


def corpus_a(data_root: Path, eval_code: Path) -> List[Entry]:
    sys.path.insert(0, str(eval_code))
    from qasm_loader import load_corpora  # unchanged evaluation loader: defines the 161-circuit set
    sel = load_corpora(data_root, max_per_corpus=PER_CORPUS, max_qubits=MAX_QUBITS, max_ops=MAX_OPS,
                       min_total=30)
    out = []
    for c in sel:
        p = Path(c.path)
        rel = str(p.relative_to(data_root)) if p.is_absolute() else str(p)
        try:
            qc = load(data_root / rel)
            if len(qc.data) > MAX_OPS:  # DEVIATIONS.md, deviation 1: same post-preparation cap as corpus B
                out.append(Entry(c.source, c.name, rel, None,
                                 f"prepared circuit has {len(qc.data)} instructions (> {MAX_OPS}) after "
                                 f"decomposing gates wider than {FLATTEN_ARITY} qubits"))
                continue
            out.append(Entry(c.source, c.name, rel, qc))
        except Exception as exc:
            out.append(Entry(c.source, c.name, rel, None, f"{type(exc).__name__}: {exc}"))
    return out


def corpus_b(data_root: Path, exclude_paths: set) -> List[Entry]:
    out = []
    for p in sorted((data_root / "veriqbench" / "dynamic").rglob("*.qasm"), key=str):
        rel = str(p.relative_to(data_root))
        if rel in exclude_paths:
            continue
        try:
            qc = load(p)
        except Exception as exc:
            out.append(Entry("VeriQBench-dynamic", p.stem, rel, None, f"{type(exc).__name__}: {exc}"))
            continue
        if qc.num_qubits <= MAX_QUBITS and len(qc.data) <= MAX_OPS:
            out.append(Entry("VeriQBench-dynamic", p.stem, rel, qc))
    return out
