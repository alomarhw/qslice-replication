"""Structure families (PROTOCOL_ICPC.md section 3.3; Deviation I-7): descriptive.

For every circuit of families/generate.py and every qubit as criterion: the slices of S-du, S-lc,
S-lcq, S-yz and S-q; their soundness under the oracle (fidelity >= 1 - 1e-6 at |0...0>); and the
ground-truth set of operations that can affect the criterion's reduced state, from the section 2.1
semantic-dependence oracle (icpc/influence.py). Per (circuit, criterion, slicer): size, size relative
to S-lc, sound, and for S-q the removable operations (in S-lc but outside the ground truth) and how
many of them S-q removes. "Sound but not minimal" = sound and containing a removable operation.
Outputs (results/icpc/families/): rows.csv, excluded.json.
Usage (from experiments/): python icpc/families_run.py [--workers 6]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
SLICERS = ["du", "lc", "lcq", "yz", "q"]
OUT = HERE / "results" / "icpc" / "families"


def _worker(job):
    family, name = job
    from common.evaluate import materialise
    from families.generate import families
    from icpc import oracle_icpc as oi
    from icpc.influence import influence, influence_sets
    from slicers.registry import NotApplicable, Slicers

    qc = next(c for f, n, c in families() if f == family and n == name)
    t0 = time.time()
    n, nops = qc.num_qubits, len(qc.data)
    try:
        base = oi.reduced_states(qc, range(n))
        gt = influence_sets(influence(qc), n)
    except oi.OracleError as exc:
        return {"excluded": f"oracle: {exc}", "family": family, "circuit": name}
    s = Slicers(qc, f"{family}:{name}")
    rows, cache = [], {}
    for t in range(n):
        sl = {}
        for m in SLICERS:
            try:
                sl[m] = s.get(m)(t)
            except NotApplicable:
                sl[m] = None
        lc = sl["lc"]
        removable = lc - gt[t]
        for m, x in sl.items():
            if x is None:
                rows.append({"family": family, "circuit": name, "target": t, "slicer": m, "applicable": 0})
                continue
            key = frozenset(x)
            if key not in cache:
                cache[key] = oi.reduced_states(materialise(qc, key), range(n))
            sound = int(oi.uhlmann_fidelity(base[t], cache[key][t]) >= 1 - oi.FIDELITY_EPS)
            row = {"family": family, "circuit": name, "n_qubits": n, "n_ops": nops, "target": t, "slicer": m,
                   "applicable": 1, "size": len(x), "size_rel_lc": len(x) / len(lc) if lc else 1.0, "sound": sound,
                   "n_ground_truth": len(gt[t]), "n_removable": len(removable),
                   "removed_removable": len(removable - x), "missed_ground_truth": len(gt[t] - x),
                   "sound_not_minimal": int(sound and bool(x & removable))}
            rows.append(row)
    return {"rows": rows, "seconds": time.time() - t0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    from families.generate import families
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = sorted(((f, n) for f, n, _ in families()),
                  key=lambda j: -next(len(c.data) * c.num_qubits for f, n, c in families() if (f, n) == j))
    rows, excluded, t0 = [], [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(_worker, j): j for j in jobs}
        for i, fut in enumerate(as_completed(futs), 1):
            res = fut.result()
            if "excluded" in res:
                excluded.append(res)
            else:
                rows += res["rows"]
            if i % 10 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} circuits, {time.time() - t0:.0f}s", flush=True)
    rows.sort(key=lambda r: (r["family"], r["circuit"], r["target"], SLICERS.index(r["slicer"])))
    with open(OUT / "rows.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)
    (OUT / "excluded.json").write_text(json.dumps(excluded, indent=2))
    print(f"rows {len(rows)}; excluded {len(excluded)}; wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
