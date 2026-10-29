"""Deviation I-24: the nesting D ⊆ QDG ⊆ QPDG, and the dependence set D as a slice.

Per RQ1 pair (circuit, criterion qubit t) of corpus A: D is the dependence set of icpc/influence.py, the QDG and
QPDG slices are the registry's `lc` and `yz`. Check 2 asserts D ⊆ QDG ⊆ QPDG and records equalities; Check 1
materialises the circuit restricted to D, as RQ1 materialises a slice, and applies the RQ1 oracle unchanged.
Usage (from experiments/): python icpc/nesting.py --data-root ../data --eval-code ../selection
  -> results/icpc/nesting/pairs.csv, summary.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
OUT = HERE / "results" / "icpc" / "nesting"


def _worker(job):
    corpus, name, rel, data_root = job
    from common.corpus import load
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from icpc.influence import influence, influence_sets
    from slicers.registry import NotApplicable, Slicers

    qc = load(Path(data_root) / rel)
    n, nops = qc.num_qubits, len(qc.data)
    try:
        base = oi.reduced_states(qc, range(n))
        inf_by_q = influence_sets(influence(qc), n)
    except oi.OracleError as exc:
        return {"excluded": f"oracle: {exc}", "path": rel}
    s = Slicers(qc, name)
    rows = []
    for t in range(n):
        D = frozenset(inf_by_q[t])
        lc = frozenset(s.get("lc")(t))
        try:
            yz = frozenset(s.get("yz")(t))
        except NotApplicable:
            yz = None
        f = oi.uhlmann_fidelity(base[t], oi.reduced_states(materialise(qc, D), [t])[t])
        rows.append({"corpus": corpus, "circuit": name, "path": rel, "n_qubits": n, "n_ops": nops, "target": t,
                     "d": len(D), "qdg": len(lc), "qpdg": "" if yz is None else len(yz),
                     "d_in_qdg": int(D <= lc), "qdg_in_qpdg": "" if yz is None else int(lc <= yz),
                     "d_eq_qdg": int(D == lc), "qdg_eq_qpdg": "" if yz is None else int(lc == yz),
                     "d_fidelity": f, "d_sound": int(f >= 1 - oi.FIDELITY_EPS)})
    return {"rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--eval-code", required=True)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    from common.corpus import corpus_a
    root = Path(a.data_root).resolve()
    A = corpus_a(root, Path(a.eval_code))
    jobs = [(e.corpus, e.name, e.path, str(root)) for e in A if e.qc is not None]
    jobs.sort(key=lambda j: -next(len(e.qc.data) * e.qc.num_qubits for e in A if e.path == j[2]))
    rows, excluded, t0 = [], [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for i, res in enumerate(ex.map(_worker, jobs, chunksize=1), 1):
            if "excluded" in res:
                excluded.append(res)
            else:
                rows += res["rows"]
            if i % 20 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} circuits, {time.time() - t0:.0f}s", flush=True)
    rows.sort(key=lambda r: (r["path"], r["target"]))
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "pairs.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    yz = [r for r in rows if r["qpdg"] != ""]
    summ = {"pairs": len(rows), "excluded": excluded,
            "d_in_qdg": sum(r["d_in_qdg"] for r in rows), "qdg_in_qpdg": sum(r["qdg_in_qpdg"] for r in yz),
            "qpdg_pairs": len(yz), "d_eq_qdg": sum(r["d_eq_qdg"] for r in rows),
            "qdg_eq_qpdg": sum(r["qdg_eq_qpdg"] for r in yz), "d_sound": sum(r["d_sound"] for r in rows),
            "d_unsound": [{k: r[k] for k in ("path", "target", "d", "qdg", "d_fidelity")} for r in rows if not r["d_sound"]],
            "violations": [{k: r[k] for k in ("path", "target", "d", "qdg", "qpdg")} for r in rows
                           if not r["d_in_qdg"] or r["qdg_in_qpdg"] == 0]}
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps({k: v for k, v in summ.items() if k not in ("d_unsound", "violations")}, indent=1),
          f"\nunsound D: {len(summ['d_unsound'])}; violations: {len(summ['violations'])}; {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
