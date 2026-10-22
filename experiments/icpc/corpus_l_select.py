"""Select corpus L (PROTOCOL_ICPC.md section 3.5) from sizes only, before any slicer runs on it.

Every circuit in qasmbench/ (full), mqtbench/ and veriqbench/ with 15-20 qubits and at most 1,000
instructions after the corpus-A preparation (common.corpus.load); de-duplicated by (name, qubits,
instructions); sorted by (qubits, instructions, path); at most 40 per corpus, smallest first.
Declared qubit counts (qreg sums) are read first so that files outside 15-20 qubits are never parsed.
Writes results/icpc/corpus_l/corpus_l.json (selected + excluded with reasons).
Usage (from experiments/): python icpc/corpus_l_select.py --data-root ../data
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

QMIN, QMAX, MAX_INSTR, PER_CORPUS = 15, 20, 1000, 40
CORPORA = {"qasmbench": "QASMBench", "mqtbench": "MQT Bench", "veriqbench": "VeriQBench"}
QREG = re.compile(r"^\s*qreg\s+\w+\s*\[\s*(\d+)\s*\]", re.M)


def declared_qubits(text: str) -> int:
    return sum(int(n) for n in QREG.findall(text))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--out", default=str(HERE / "results" / "icpc" / "corpus_l"))
    a = ap.parse_args()
    from common.corpus import load
    root, out = Path(a.data_root).resolve(), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    selected, excluded = [], []
    for sub, corpus in CORPORA.items():
        cands, seen = [], set()
        for p in sorted((root / sub).rglob("*.qasm"), key=str):
            rel = str(p.relative_to(root))
            try:
                nq = declared_qubits(p.read_text(errors="ignore"))
            except OSError as exc:
                excluded.append({"corpus": corpus, "path": rel, "reason": f"read: {exc}"})
                continue
            if not QMIN <= nq <= QMAX:
                continue
            try:
                qc = load(p)
            except Exception as exc:  # noqa: BLE001 - a circuit that does not load is excluded and listed
                excluded.append({"corpus": corpus, "path": rel, "reason": f"load: {type(exc).__name__}: {str(exc)[:160]}"})
                continue
            n_ops = len(qc.data)
            if not QMIN <= qc.num_qubits <= QMAX:
                continue
            if n_ops > MAX_INSTR:
                excluded.append({"corpus": corpus, "path": rel, "reason": f"{n_ops} instructions after preparation (> {MAX_INSTR})"})
                continue
            key = (p.stem, qc.num_qubits, n_ops)
            if key in seen:
                excluded.append({"corpus": corpus, "path": rel, "reason": "duplicate (name, qubits, instructions)"})
                continue
            seen.add(key)
            dyn = any(i.operation.name in ("measure", "reset", "if_else") for i in qc.data)
            cands.append({"corpus": corpus, "name": p.stem, "path": rel, "n_qubits": qc.num_qubits,
                          "n_ops": n_ops, "dynamic_ops": int(dyn)})
        cands.sort(key=lambda c: (c["n_qubits"], c["n_ops"], c["path"]))
        selected += cands[:PER_CORPUS]
        for c in cands[PER_CORPUS:]:
            excluded.append({"corpus": corpus, "path": c["path"], "reason": f"over the {PER_CORPUS}-per-corpus cap"})
    (out / "corpus_l.json").write_text(json.dumps({"rule": __doc__.split("\n\n")[1], "selected": selected,
                                                   "excluded": excluded}, indent=1))
    by = {c: sum(1 for s in selected if s["corpus"] == c) for c in CORPORA.values()}
    print(f"selected {len(selected)} circuits {by}; excluded {len(excluded)}; wrote {out / 'corpus_l.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
