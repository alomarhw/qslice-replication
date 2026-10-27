"""Foundations measures (Deviation I-17, exploratory): four-edge graph with and without closure, undirected slicing,
seeding, histogram checks of unsound slices, forward slices and duality.

Per corpus-A circuit and criterion qubit t, at |0...0>, scored as in icpc/rq1_run.py:
  lc        QDG backward slice (reproduces the committed RQ1 records)
  4e        four-edge graph, seeded at t's last operation (= committed 4e_fixed)
  4e_nocl   four-edge graph without the transitive entanglement closure                       (J1)
  lc_all    QDG backward slice seeded at every operation on t                                   (J3)
  und_qdg   undirected reachability in the QDG from every operation on t                        (J2)
  und_4e    undirected reachability in the four-edge graph from every operation on t  (J2)
Per unsound du / cpdg slice: whether the criterion's Z-basis distribution still matches            (J5)
Per operation k: forward QDG slice (final qubits reachable from k) vs influence(qc)[k] (forward ground
truth), and duality: q in F(k)  <=>  k in lc(q)                                                      (S1)
Output: results/icpc/foundations/ (pairs.csv, forward.csv, summary.json).
Usage (from experiments/): python icpc/foundations_eval.py --data-root ../data --eval-code ../selection [--workers 8]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP))


def _und(edges, n, seeds):
    adj = {i: set() for i in range(n)}
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)
    seen, st = set(), list(seeds)
    while st:
        x = st.pop()
        if x in seen:
            continue
        seen.add(x)
        st.extend(adj[x])
    return seen


def _back(edges, seeds):
    pred = {}
    for u, v in edges:
        pred.setdefault(v, set()).add(u)
    seen, st = set(), list(seeds)
    while st:
        x = st.pop()
        if x in seen:
            continue
        seen.add(x)
        st.extend(pred.get(x, ()))
    return seen


def _fwd(edges, seeds):
    succ = {}
    for u, v in edges:
        succ.setdefault(u, set()).add(v)
    seen, st = set(), list(seeds)
    while st:
        x = st.pop()
        if x in seen:
            continue
        seen.add(x)
        st.extend(succ.get(x, ()))
    return seen


def _worker(job):
    corpus, name, rel, data_root = job
    import numpy as np
    from common.corpus import load
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from icpc.cpdg import cpdg_slice
    from icpc.influence import influence, influence_sets
    from slicers.registry import Slicers
    import src.qdg as fq

    qc = load(Path(data_root) / rel)
    n, L = qc.num_qubits, len(qc.data)
    try:
        base = oi.reduced_states(qc, range(n))
        inf = influence(qc)
        dep = influence_sets(inf, n)
    except oi.OracleError as exc:
        return {"excluded": str(exc)[:200], "path": rel}
    s = Slicers(qc, name)
    qdg_edges = [(u, v) for u, v in s.causal.graph.edges()]
    g4 = s._four_qdg()
    en4 = None
    from src.slicer import SlicerVariant, VARIANT_EDGE_TYPES
    en4 = VARIANT_EDGE_TYPES[SlicerVariant.QSLICE_FULL]
    e4 = [(u, v) for u, v, d in g4.graph.edges(data=True) if d.get("types", set()) & en4]
    # four-edge graph without the transitive closure
    orig = fq._add_transitive_entanglement_edges
    fq._add_transitive_entanglement_edges = lambda *a, **k: None
    try:
        g4n = fq.qdg_from_circuit(qc, "fourEdgeNoClosure")
    finally:
        fq._add_transitive_entanglement_edges = orig
    e4n = [(u, v) for u, v, d in g4n.graph.edges(data=True) if d.get("types", set()) & en4]
    on = {t: [k for k, inst in enumerate(qc.data) if t in {qc.find_bit(q).index for q in inst.qubits}] for t in range(n)}

    cache = {}

    def score(x, t):
        x = frozenset(x)
        if x not in cache:
            cache[x] = oi.reduced_states(materialise(qc, x), range(n))
        f = oi.uhlmann_fidelity(base[t], cache[x][t])
        hit = len(x & dep[t])
        zmatch = bool(abs(base[t][0, 0].real - cache[x][t][0, 0].real) < 1e-6)
        return {"size": len(x) / max(L, 1), "sound": int(f >= 1 - oi.FIDELITY_EPS),
                "recall": hit / len(dep[t]) if dep[t] else 1.0, "precision": hit / len(x) if x else 1.0, "zmatch": int(zmatch)}

    rows = []
    lc = {}
    for t in range(n):
        if not on[t]:
            continue
        sl = {"lc": s.lc(t), "4e": s.four_fixed(t), "4e_nocl": _back(e4n, {max(on[t])}),
              "lc_all": _back(qdg_edges, set(on[t])), "und_qdg": _und(qdg_edges, L, on[t]), "und_4e": _und(e4, L, on[t]),
              "du": s.du(t), "cpdg": cpdg_slice(qc, t)}
        lc[t] = sl["lc"]
        for m, x in sl.items():
            rows.append({"path": rel, "target": t, "slicer": m, "eq_lc": int(set(x) == set(sl["lc"]))} | score(x, t))
    # forward (S1): final qubits reachable from k in the QDG = qubits whose last operation is reachable
    last = {t: max(on[t]) for t in range(n) if on[t]}
    fwd = []
    for k in range(L):
        reach = _fwd(qdg_edges, {k})
        F = {t for t, lk in last.items() if lk in reach}
        dual = {t for t in lc if k in lc[t]}
        truth = set(inf.get(k, set()))
        fwd.append({"path": rel, "op": k, "n_fwd": len(F), "n_truth": len(truth), "complete": int(truth <= F),
                    "dual_ok": int(F == dual), "precision": len(truth & F) / len(F) if F else 1.0})
    return {"rows": rows, "fwd": fwd}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--eval-code", default="../selection")
    ap.add_argument("--out", default=str(EXP / "results" / "icpc" / "foundations"))
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    from common.corpus import corpus_a
    root = Path(a.data_root).resolve()
    A = [e for e in corpus_a(root, Path(a.eval_code)) if e.qc is not None]
    jobs = sorted([(e.corpus, e.name, e.path, str(root)) for e in A], key=lambda j: j[2])
    rows, fwd, exc, t0 = [], [], [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for i, f in enumerate(as_completed([ex.submit(_worker, j) for j in jobs]), 1):
            r = f.result()
            if "excluded" in r:
                exc.append(r)
            else:
                rows += r["rows"]
                fwd += r["fwd"]
            if i % 20 == 0:
                print(f"  {i}/{len(jobs)} {time.time() - t0:.0f}s", flush=True)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for nm, rs in (("pairs.csv", rows), ("forward.csv", fwd)):
        with open(out / nm, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rs[0]))
            w.writeheader()
            w.writerows(rs)
    import statistics as stt
    summ = {}
    for m in sorted({r["slicer"] for r in rows}):
        x = [r for r in rows if r["slicer"] == m]
        uns = [r for r in x if not r["sound"]]
        summ[m] = {"n": len(x), "unsound": len(uns), "size": stt.mean(r["size"] for r in x),
                   "recall": stt.mean(r["recall"] for r in x), "precision": stt.mean(r["precision"] for r in x),
                   "equal_to_lc": sum(r["eq_lc"] for r in x), "unsound_but_z_matches": sum(r["zmatch"] for r in uns)}
    summ["forward"] = {"ops": len(fwd), "complete": sum(r["complete"] for r in fwd), "dual_ok": sum(r["dual_ok"] for r in fwd),
                       "precision": stt.mean(r["precision"] for r in fwd)}
    summ["excluded"] = len(exc)
    (out / "summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
