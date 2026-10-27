"""Convergence of the sampled dependence ground truth (Deviation I-19, exploratory; review item 2).

The ground truth of section 2.1 (icpc/influence.py) perturbs each instruction at |0...0> and 10 Haar-random
product inputs with 2 Haar-random unitaries. Here the same procedure runs in four cumulative stages on corpus A:
  0  the original inputs and perturbations (same seeds): must reproduce influence() exactly (asserted);
  1  + 6 more perturbations per instruction at the same inputs;
  2  + 30 more Haar-random product inputs (all 8 perturbations);
  3  + 10 entangled inputs, each prepared by a brickwork circuit of n layers of Haar-random two-qubit gates.
Per (circuit, criterion qubit) it records the dependences each stage adds, and each slicer's recall and
precision against the stage-0 and stage-3 sets. Every dependence must lie in the QDG slice (Theorem 1); the
run counts any that do not. Soundness is judged by the oracle and does not depend on this set.
Outputs (results/icpc/gt_convergence/): pairs.csv (one row per pair x slicer), new_deps.csv (one row per
dependence found after stage 0).
Usage (from experiments/): python icpc/gt_convergence.py --data-root ../data --eval-code ../selection [--workers 14]
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
OUT = HERE / "results" / "icpc" / "gt_convergence"
EXTRA_PERT, EXTRA_PRODUCT, N_ENTANGLED = 6, 30, 10
SLICERS = ("du", "cpdg", "lc", "yz", "yzf", "lcq", "q")


def _prefixed(qc, prep):
    """qc preceded by an input preparation: None, a product list of 1-qubit unitaries, or a gate list."""
    from qiskit.circuit.library import UnitaryGate
    from icpc import oracle_icpc as oi
    if prep is None or isinstance(prep, list) and prep and isinstance(prep[0], np.ndarray):
        return oi.with_input(qc, prep)
    out = qc.copy_empty_like()
    for u, qs in prep:
        out.append(UnitaryGate(u, check_input=False), [out.qubits[q] for q in qs])
    for inst in qc.data:
        out.append(inst)
    return out


def _brickwork(n, rng):
    from icpc import oracle_icpc as oi
    gates = []
    for layer in range(n):
        for a in range(layer % 2, n - 1, 2):
            gates.append((oi.haar_unitary(4, rng), (a, a + 1)))
    return gates


def _stages(qc):
    """{(k, q): first stage that finds k influencing q}, with stage 0 identical to influence()."""
    from icpc import oracle_icpc as oi
    from icpc.influence import N_PERTURBATIONS, SEED, SKIP, _changed, _inputs
    n = qc.num_qubits
    qs = range(n)
    inputs0 = _inputs(n, SEED)
    rng = np.random.default_rng(SEED + 1)
    pert0 = {}
    for k, inst in enumerate(qc.data):
        if inst.operation.name not in SKIP:
            pert0[k] = [oi.haar_unitary(2 ** len(inst.qubits), rng) for _ in range(N_PERTURBATIONS)]
    rng2 = np.random.default_rng(SEED + 7)
    pert1 = {k: [oi.haar_unitary(2 ** len(qc.data[k].qubits), rng2) for _ in range(EXTRA_PERT)] for k in pert0}
    more = [oi.haar_product_input(n, rng2) for _ in range(EXTRA_PRODUCT)]
    ent = [_brickwork(n, rng2) for _ in range(N_ENTANGLED)] if n > 1 else []
    flips = {k: oi.flip_measurement_outcome(qc, k) for k, inst in enumerate(qc.data) if inst.operation.name == "measure"}
    found = {}
    plan = [(0, inputs0, "p0"), (1, inputs0, "p1"), (2, more, "all"), (3, ent, "all")]
    for stage, inputs, which in plan:
        for prep in inputs:
            base = oi.reduced_states(_prefixed(qc, prep), qs)
            for k in pert0:
                if sum((k, q) in found for q in qs) == n:
                    continue
                us = pert0[k] if which == "p0" else pert1[k] if which == "p1" else pert0[k] + pert1[k]
                for u in us:
                    for q in _changed(base, oi.reduced_states(_prefixed(oi.insert_unitary_after(qc, k, u), prep), qs)):
                        found.setdefault((k, q), stage)
                if which != "p1" and flips.get(k) is not None:
                    for q in _changed(base, oi.reduced_states(_prefixed(flips[k], prep), qs)):
                        found.setdefault((k, q), stage)
    return found


def _job(job):
    corpus, name, rel, data_root, eval_code = job
    from common.corpus import load
    from icpc import oracle_icpc as oi
    from icpc.cpdg import cpdg_slice
    from icpc.influence import influence, influence_sets
    from slicers.registry import NotApplicable, Slicers
    from slicers.yuzhao import yuzhao_flow_slice
    qc = load(Path(data_root) / rel)
    n = qc.num_qubits
    try:
        found = _stages(qc)
        ref = influence_sets(influence(qc), n)
    except oi.OracleError as exc:
        return {"excluded": str(exc)[:200], "path": rel}
    s0 = {t: {k for (k, q), st in found.items() if q == t and st == 0} for t in range(n)}
    assert s0 == ref, f"stage 0 does not reproduce influence() on {rel}"
    s = Slicers(qc, name)
    rows, new = [], []
    for t in range(n):
        dep = {st: {k for (k, q), x in found.items() if q == t and x <= st} for st in range(4)}
        lc = s.lc(t)
        for (k, q), st in found.items():
            if q == t and st > 0:
                new.append({"corpus": corpus, "circuit": name, "path": rel, "target": t, "position": k,
                            "gate": qc.data[k].operation.name, "stage": st, "in_qdg": int(k in lc)})
        for sl_name in SLICERS:
            try:
                sl = (cpdg_slice(qc, t) if sl_name == "cpdg" else yuzhao_flow_slice(qc, t, HERE)
                      if sl_name == "yzf" else s.get(sl_name)(t))
            except NotApplicable:
                continue
            r = {"corpus": corpus, "circuit": name, "path": rel, "n_qubits": n, "n_ops": len(qc.data), "target": t,
                 "slicer": sl_name, "size": len(sl)}
            for st in (0, 3):
                d = dep[st]
                r[f"n_dep{st}"] = len(d)
                r[f"recall{st}"] = len(sl & d) / len(d) if d else 1.0
                r[f"precision{st}"] = len(sl & d) / len(sl) if sl else 1.0
            r.update({f"added{st}": len(dep[st]) - len(dep[st - 1]) for st in (1, 2, 3)})
            rows.append(r)
    return {"rows": rows, "new": new, "dep_outside_qdg": sum(1 for (k, q) in found if k not in s.lc(q))}


def _write(name, rows):
    with open(OUT / name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)) or ["none"])
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--eval-code", default="../selection")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    root = str(Path(a.data_root).resolve())
    OUT.mkdir(parents=True, exist_ok=True)
    from common.corpus import corpus_a
    A = [e for e in corpus_a(Path(root), Path(a.eval_code)) if e.qc is not None]
    if a.limit:
        A = A[: a.limit]
    t0 = time.time()
    rows, new, outside, excl = [], [], 0, []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(_job, (e.corpus, e.name, e.path, root, a.eval_code)) for e in A]
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            if "excluded" in r:
                excl.append(r)
                continue
            rows += r["rows"]
            new += r["new"]
            outside += r["dep_outside_qdg"]
            if i % 20 == 0:
                print(f"  {i}/{len(A)} circuits, {time.time() - t0:.0f}s", flush=True)
    _write("pairs.csv", sorted(rows, key=lambda r: (r["path"], r["target"], r["slicer"])))
    _write("new_deps.csv", new)
    lc = [r for r in rows if r["slicer"] == "lc"]
    print(f"pairs {len(lc)}; excluded {len(excl)}; deps stage0 {sum(r['n_dep0'] for r in lc)}, stage3 "
          f"{sum(r['n_dep3'] for r in lc)}; new {len(new)} (outside QDG {sum(1 - x['in_qdg'] for x in new)}); "
          f"all deps outside QDG {outside}; {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
