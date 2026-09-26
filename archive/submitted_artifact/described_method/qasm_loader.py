"""qasm_loader.py — load REAL benchmark circuits (QASMBench) for the slicing study.

QASMBench (PNNL) ships as OpenQASM 2.0 files under data/qasmbench/small/. We load the algorithmic
(non-transpiled) circuits, strip terminal measurements/barriers to expose the unitary core (slicing
soundness is evaluated on the quantum state, so we need a statevector-simulable body), and return a
uniform corpus the experiment consumes. Circuits with mid-circuit measurement / classical feedback
are flagged ``unitary=False`` so the caller can route them to the density-matrix path or skip them.
"""

from __future__ import annotations

import glob
import os
import re
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from qiskit import qasm2
from qiskit import QuantumCircuit

QASMBENCH_DIR = Path(__file__).parent / "data" / "qasmbench"  # contains small/ medium/ large/
MQTBENCH_DIR = Path(__file__).parent / "data" / "mqtbench"     # flat dir of generated MQT Bench circuits
VERIQBENCH_DIR = Path(__file__).parent / "data" / "veriqbench"  # combinational/ dynamic/ sequential/ variational/
CATEGORIES = ("small", "medium", "large")
VERIQ_FAMILIES = ("combinational", "dynamic", "sequential", "variational")


def _size_bin(nq: int) -> str:
    """Bin a circuit into small/medium/large by qubit count (matches the QASMBench split)."""
    return "small" if nq <= 10 else ("medium" if nq <= 27 else "large")

_NONUNITARY = {"measure", "reset"}
_QREG_RE = re.compile(r"qreg\s+\w+\s*\[\s*(\d+)\s*\]", re.IGNORECASE)


def _peek_ops(path: Path) -> int:
    """Rough upper bound on gate count = number of non-empty, non-header lines. Lets us skip a
    600k-gate circuit before asking qiskit to parse it."""
    try:
        n = 0
        with open(path, "r", errors="ignore") as fh:
            for line in fh:
                s = line.strip()
                if s and not s.startswith(("//", "OPENQASM", "include", "qreg", "creg", "gate ")):
                    n += 1
        return n
    except Exception:
        return 0


def _peek_qubits(path: Path) -> int:
    """Cheap upper bound on qubit count from the OpenQASM text (sum of qreg sizes), so we can skip a
    10000-qubit circuit WITHOUT asking qiskit to parse a 100 MB file."""
    total = 0
    try:
        with open(path, "r", errors="ignore") as fh:
            for line in fh:
                m = _QREG_RE.search(line)
                if m:
                    total += int(m.group(1))
    except Exception:
        return 0
    return total


def _strip_for_statevector(qc: QuantumCircuit) -> tuple[QuantumCircuit, bool]:
    """Return (unitary_core, is_pure_unitary). Strips terminal measurements/barriers (the unitary body
    is still exactly simulable) and reports whether the circuit is unitary *up to* terminal readout.

    ``pure`` is False only for genuinely non-unitary dynamics — MID-CIRCUIT measurement/reset (a
    measure/reset followed by a later gate on the same qubit) or classical feedback — which the
    statevector path cannot represent.
    """
    qidx = {q: i for i, q in enumerate(qc.qubits)}
    data = list(qc.data)
    # Precompute the LAST op index touching each qubit — O(ops) — so the mid-circuit test below is
    # O(ops) instead of O(ops²) (the latter hangs on 600k-gate circuits like factor247_n15).
    last_touch: dict = {}
    for i, ci in enumerate(data):
        for q in ci.qubits:
            if q in qidx:
                last_touch[qidx[q]] = i
    # A measurement/reset is "mid-circuit" if some later op touches one of its qubits.
    pure = True
    for i, ci in enumerate(data):
        cond = getattr(ci.operation, "condition", None) or getattr(ci.operation, "_condition", None)
        if cond is not None:
            pure = False
            break
        if ci.operation.name in _NONUNITARY:
            if any(last_touch.get(qidx[q], i) > i for q in ci.qubits if q in qidx):
                pure = False
                break

    out = QuantumCircuit(qc.num_qubits, name=qc.name)
    out.global_phase = qc.global_phase
    for ci in data:
        if ci.operation.name in _NONUNITARY or ci.operation.name == "barrier":
            continue
        try:
            out.append(ci.operation, [out.qubits[qidx[q]] for q in ci.qubits], [])
        except Exception:
            pure = False
    return out, pure


def load_qasmbench_corpus(max_qubits: int = 12, min_qubits: int = 2,
                          limit: Optional[int] = None,
                          require_unitary: bool = True,
                          categories: Sequence[str] = ("small",),
                          max_ops: Optional[int] = None,
                          directory: Optional[Path] = None) -> List[Dict]:
    """Load QASMBench circuits as ``[{id, qc, n_qubits, n_ops, source, category, unitary}]``.

    ``categories`` selects among ``small`` / ``medium`` / ``large`` (the subfolders under
    ``data/qasmbench``). ``qc`` is the unitary core (terminal measurements stripped) so the slicing
    analysis can use exact statevector semantics. Circuits are skipped when:
      • a cheap text peek of total qreg width already exceeds ``max_qubits`` (so a 10000-qubit large
        circuit is never handed to the parser — exact statevector simulation is 2**n);
      • the parsed circuit is outside ``[min_qubits, max_qubits]``;
      • ``require_unitary`` and it has mid-circuit measurement / classical feedback.
    Note: ``max_qubits`` is bounded by exact simulation, so the medium/large sets mostly matter for
    structural analysis (slice size, edge counts) or runs on a larger simulator.
    """
    base = Path(directory or QASMBENCH_DIR)
    corpus: List[Dict] = []
    for cat in categories:
        cat_dir = base / cat if (base / cat).is_dir() else base
        for path in sorted(glob.glob(str(cat_dir / "*.qasm"))):
            name = os.path.basename(path).replace(".qasm", "")
            if _peek_qubits(Path(path)) > max_qubits:   # skip wide circuits before parsing
                continue
            if max_ops is not None and _peek_ops(Path(path)) > max_ops * 3:  # skip 600k-gate circuits cheaply
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    raw = qasm2.load(path, custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
            except Exception:
                continue
            if not (min_qubits <= raw.num_qubits <= max_qubits):
                continue
            core, pure = _strip_for_statevector(raw)
            if require_unitary and not pure:
                continue
            if len(core.data) == 0:
                continue
            corpus.append({
                "id": name, "qc": core, "n_qubits": core.num_qubits, "n_ops": len(core.data),
                "source": "QASMBench", "category": cat, "unitary": pure,
            })
            if limit and len(corpus) >= limit:
                return corpus
    return corpus


def load_mqt_corpus(max_qubits: int = 12, min_qubits: int = 2, require_unitary: bool = True,
                    max_ops: Optional[int] = None, limit: Optional[int] = None,
                    directory: Optional[Path] = None) -> List[Dict]:
    """Load the generated MQT Bench circuits (flat dir) — same record shape as the QASMBench loader,
    with ``source="MQT"`` and ``category`` binned by qubit count. A SECOND, independently-curated
    benchmark suite so the slicing results can be shown to replicate across benchmarks."""
    base = Path(directory or MQTBENCH_DIR)
    corpus: List[Dict] = []
    for path in sorted(glob.glob(str(base / "*.qasm"))):
        name = os.path.basename(path).replace(".qasm", "")
        if _peek_qubits(Path(path)) > max_qubits:
            continue
        if max_ops is not None and _peek_ops(Path(path)) > max_ops * 3:
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                raw = qasm2.load(path, custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
        except Exception:
            continue
        if not (min_qubits <= raw.num_qubits <= max_qubits):
            continue
        core, pure = _strip_for_statevector(raw)
        if (require_unitary and not pure) or len(core.data) == 0:
            continue
        corpus.append({"id": f"mqt_{name}", "qc": core, "n_qubits": core.num_qubits,
                       "n_ops": len(core.data), "source": "MQT", "category": _size_bin(core.num_qubits),
                       "unitary": pure})
        if limit and len(corpus) >= limit:
            break
    return corpus


def load_veriqbench_corpus(max_qubits: int = 12, min_qubits: int = 2, require_unitary: bool = True,
                           max_ops: Optional[int] = None, limit: Optional[int] = None,
                           families: Sequence[str] = VERIQ_FAMILIES,
                           directory: Optional[Path] = None) -> List[Dict]:
    """Load VeriQBench (Veri-Q/Benchmark) circuits — same record shape as the other loaders, with
    ``source="VeriQ"``. VeriQBench is a *verification* benchmark shipped as OpenQASM 2.0 under nested
    family subfolders (combinational/ dynamic/ sequential/ variational/), so we glob RECURSIVELY and
    keep the family in ``category``-adjacent ``family`` plus the qubit-binned ``category``. A THIRD,
    independently-curated suite (adds VQE/QAOA/EfficientSU2 families) to test cross-benchmark
    replication of the slicing results. The dynamic/sequential families use mid-circuit measurement /
    classical feedback and are dropped from the exact (unitary) path by ``require_unitary``."""
    base = Path(directory or VERIQBENCH_DIR)
    corpus: List[Dict] = []
    for fam in families:
        fam_dir = base / fam
        if not fam_dir.is_dir():
            continue
        for path in sorted(glob.glob(str(fam_dir / "**" / "*.qasm"), recursive=True)):
            name = os.path.basename(path).replace(".qasm", "")
            if _peek_qubits(Path(path)) > max_qubits:
                continue
            if max_ops is not None and _peek_ops(Path(path)) > max_ops * 3:
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    raw = qasm2.load(path, custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
            except Exception:
                continue
            if not (min_qubits <= raw.num_qubits <= max_qubits):
                continue
            core, pure = _strip_for_statevector(raw)
            if (require_unitary and not pure) or len(core.data) == 0:
                continue
            corpus.append({"id": f"veriq_{fam[:4]}_{name}", "qc": core, "n_qubits": core.num_qubits,
                           "n_ops": len(core.data), "source": "VeriQ", "family": fam,
                           "category": _size_bin(core.num_qubits), "unitary": pure})
            if limit and len(corpus) >= limit:
                return corpus
    return corpus


def load_combined(max_qubits: int = 12, min_qubits: int = 2, require_unitary: bool = True,
                  categories: Sequence[str] = ("small", "medium", "large"),
                  max_ops: Optional[int] = None,
                  suites: Sequence[str] = ("qasmbench", "mqt", "veriqbench")) -> List[Dict]:
    """Merge QASMBench (by category subdir), MQT (flat), and VeriQBench (family subdirs) into one
    corpus, each record tagged with its ``source``. Used for the cross-benchmark exact and structural
    runs."""
    out: List[Dict] = []
    if "qasmbench" in suites:
        out += load_qasmbench_corpus(max_qubits=max_qubits, min_qubits=min_qubits,
                                     require_unitary=require_unitary, categories=categories, max_ops=max_ops)
    if "mqt" in suites:
        out += load_mqt_corpus(max_qubits=max_qubits, min_qubits=min_qubits,
                               require_unitary=require_unitary, max_ops=max_ops)
    if "veriqbench" in suites:
        out += load_veriqbench_corpus(max_qubits=max_qubits, min_qubits=min_qubits,
                                      require_unitary=require_unitary, max_ops=max_ops)
    return out


def count_available(max_qubits: int = 9999) -> Dict[str, int]:
    """How many circuits each category has on disk (by cheap qreg peek), for reporting."""
    base = QASMBENCH_DIR
    out = {}
    for cat in CATEGORIES:
        d = base / cat
        files = glob.glob(str(d / "*.qasm")) if d.is_dir() else []
        out[cat] = sum(1 for f in files if _peek_qubits(Path(f)) <= max_qubits)
    return out


if __name__ == "__main__":
    import sys
    cats = sys.argv[1:] or ["small", "medium", "large"]
    mq = 26  # show what is at least loadable on a generous simulator
    print(f"QASMBench on disk: {count_available()} circuits total per category")
    c = load_qasmbench_corpus(max_qubits=mq, categories=cats)
    print(f"Loaded {len(c)} unitary circuits (<= {mq} qubits) across {cats}:")
    for e in c:
        print(f"  [{e['category']:6s}] {e['id']:30s} q={e['n_qubits']:3d} ops={e['n_ops']}")
