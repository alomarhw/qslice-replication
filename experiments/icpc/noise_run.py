"""Noisy simulation (PROTOCOL_ICPC.md section 7.2): what a developer sees when running a slice instead
of the full circuit on a noisy device. Descriptive; not a claim about real hardware.

Pairs: corpus-A (circuit, qubit) pairs with at most 10 qubits. Slices: S-lc and S-q (computed on the
ideal circuit, as in RQ1). The full circuit and each slice are transpiled to {u, cx} (plus measure,
reset, if_else) with optimization_level=0 and simulated with AerSimulator(method="density_matrix")
under depolarizing error p1 on every u and p2 on every cx, p2 in {1e-3, 1e-2, 3e-2}, p1 = p2/10; no
readout error. Fixed before the run (details section 7.2 leaves open):
  - terminal measurements are removed before the final density matrix is saved (the comparison is on
    reduced states, as in the oracle);
  - a circuit that still contains a measurement, reset or if_else is simulated with 1,024 shots and
    the saved density matrix is Aer's shot average (the unconditional state, estimated); a circuit
    without them needs one shot and is exact;
  - the ideal reduced state rho_q is the oracle's exact one (icpc/oracle_icpc.py).
Measures per (pair, slicer, level): D_full = TD(noisy full, ideal), D_slice = TD(noisy slice, ideal),
D_cross = TD(noisy slice, noisy full), with TD the trace distance of the criterion's 2x2 state.
Output: results/icpc/noise/pairs.csv, excluded.json.
Usage (from experiments/, noise venv): python icpc/noise_run.py --data-root ../data --eval-code ../selection
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
P2_LEVELS, MAX_QUBITS, DYN_SHOTS = (1e-3, 1e-2, 3e-2), 10, 1024
BASIS = ["u", "cx", "measure", "reset", "if_else"]
DYNAMIC = ("measure", "reset", "if_else")


def _td(a: np.ndarray, b: np.ndarray) -> float:
    return float(0.5 * np.abs(np.linalg.eigvalsh(a - b)).sum())


def _noisy_states(qc, n, p2, seed):
    from qiskit import transpile
    from qiskit.quantum_info import DensityMatrix, partial_trace
    from qiskit_aer import AerSimulator
    from qiskit_aer.noise import NoiseModel, depolarizing_error
    nm = NoiseModel()
    nm.add_all_qubit_quantum_error(depolarizing_error(p2 / 10, 1), ["u"])
    nm.add_all_qubit_quantum_error(depolarizing_error(p2, 2), ["cx"])
    t = transpile(qc, basis_gates=BASIS, optimization_level=0)
    dyn = any(i.operation.name in DYNAMIC for i in t.data)
    t.save_density_matrix()
    shots = DYN_SHOTS if dyn else 1
    res = AerSimulator(method="density_matrix", noise_model=nm, max_parallel_threads=1, seed_simulator=seed).run(
        t, shots=shots).result()
    rho = DensityMatrix(res.data()["density_matrix"])
    return {q: np.asarray(partial_trace(rho, [k for k in range(n) if k != q]).data) for q in range(n)}, shots


def _worker(job):
    corpus, name, rel, data_root = job
    from common.corpus import load
    from common.evaluate import materialise
    from common.oracle import terminal_measurements
    from icpc import oracle_icpc as oi
    from slicers.registry import Slicers

    t0 = time.time()
    qc = load(Path(data_root) / rel)
    n, nops = qc.num_qubits, len(qc.data)
    try:
        ideal = oi.reduced_states(qc, range(n))
    except oi.OracleError as exc:
        return {"excluded": f"oracle: {exc}", "corpus": corpus, "circuit": name, "path": rel}
    term = set(terminal_measurements(qc))
    s = Slicers(qc, name)
    slices = {(t, m): frozenset(s.get(m)(t)) for t in range(n) for m in ("lc", "q")}
    versions = {"full": frozenset(range(nops))} | {sl: sl for sl in set(slices.values())}
    seed = int(hashlib.sha256(f"20261022:noise:{rel}".encode()).hexdigest()[:8], 16)
    rows = []
    for p2 in P2_LEVELS:
        noisy, shots = {}, {}
        for key, pos in versions.items():
            noisy[key], shots[key] = _noisy_states(materialise(qc, set(pos) - term), n, p2, seed)
        for (t, m), sl in slices.items():
            rows.append({"corpus": corpus, "circuit": name, "path": rel, "n_qubits": n, "n_ops": nops,
                         "target": t, "slicer": m, "p2": p2, "slice_size": len(sl), "removed": nops - len(sl),
                         "D_full": _td(noisy["full"][t], ideal[t]), "D_slice": _td(noisy[sl][t], ideal[t]),
                         "D_cross": _td(noisy[sl][t], noisy["full"][t]),
                         "shots_full": shots["full"], "shots_slice": shots[sl]})
    return {"rows": rows, "seconds": time.time() - t0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--eval-code", required=True)
    ap.add_argument("--out", default=str(HERE / "results" / "icpc" / "noise"))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None, help="debug only: first N circuits")
    a = ap.parse_args()
    from common.corpus import corpus_a
    root, out = Path(a.data_root).resolve(), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    A = corpus_a(root, Path(a.eval_code))
    excluded = [{"corpus": e.corpus, "circuit": e.name, "path": e.path, "reason": f"load: {e.error}"} for e in A if e.qc is None]
    excluded += [{"corpus": e.corpus, "circuit": e.name, "path": e.path, "reason": f"{e.qc.num_qubits} qubits (> {MAX_QUBITS})"}
                 for e in A if e.qc is not None and e.qc.num_qubits > MAX_QUBITS]
    jobs = [(e.corpus, e.name, e.path, str(root)) for e in A if e.qc is not None and e.qc.num_qubits <= MAX_QUBITS][: a.limit]
    rows, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for i, res in enumerate(ex.map(_worker, jobs, chunksize=1), 1):
            if "excluded" in res:
                excluded.append({k: res[k] for k in ("corpus", "circuit", "path")} | {"reason": res["excluded"]})
            else:
                rows += res["rows"]
            if i % 10 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} circuits, {time.time() - t0:.0f}s", flush=True)
    rows.sort(key=lambda r: (r["path"], r["target"], r["slicer"], r["p2"]))
    with open(out / "pairs.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (out / "excluded.json").write_text(json.dumps(excluded, indent=2))
    print(f"rows {len(rows)}; circuits run {len(jobs)}; excluded {len(excluded)}; wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
