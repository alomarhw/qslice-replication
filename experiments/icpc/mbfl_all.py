"""MBFL for every rule (Deviation I-19, exploratory; review item 6).

icpc/mbfl.py reports EXAM over all instructions and filtered by S-q and S-lc. This run uses the same units, tests,
MBFL mutants, Ochiai scores and EXAM definitions (imported unchanged) and filters by every rule: S-du, S-cpdg,
S-lc, S-yz, S-q. S-q and S-lc are the slices icpc/mbfl.py used (S-lc is asserted equal when recomputed); the others
are computed on P.
It also reports the operations examined before the first fault instruction (EXAM best x slice size) and, per
rule, the EXAM of the expected position of the fault in a random order of the same slice (a size-only baseline).
Output: results/icpc/mbfl/units_all_rules.csv.
Usage (from experiments/): python icpc/mbfl_all.py --data-root ../data [--workers 12]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from icpc.mbfl import EPS, N_HAAR, OUT, _build, _z, exam, jobs, mbfl_mutants  # noqa: E402

RULES = ("du", "cpdg", "lc", "yz", "q")


def _worker(job):
    key, units, data_root = job
    from icpc import oracle_icpc as oi
    from icpc.cpdg import cpdg_slice
    from slicers.registry import Slicers
    P, R = _build(key, data_root)
    n = P.num_qubits
    rng = np.random.default_rng(int(hashlib.sha256(f"20261026:mbfl:{key}".encode()).hexdigest()[:12], 16))
    preps = [None] + [oi.haar_product_input(n, rng) for _ in range(N_HAAR)]
    try:
        zP, zR = _z(P, preps, n), _z(R, preps, n)
        muts = mbfl_mutants(P)
        zM = [(k, _z(m, preps, n)) for k, _, m in muts]
    except oi.OracleError as exc:
        return [u["meta"] | {"excluded": f"oracle: {str(exc)[:120]}"} for u in units]
    s = Slicers(P, str(key))
    rows = []
    for u in units:
        t = u["target"]
        # S-q and S-lc are the slices icpc/mbfl.py used; S-q's pruning decisions at its 1e-9 thresholds can differ
        # between runs (Deviation I-19), so a recomputed S-q is only compared
        sl = {"du": s.du(t), "cpdg": cpdg_slice(P, t), "lc": set(u["slices"]["lc"]), "yz": s.yz(t), "q": set(u["slices"]["q"])}
        assert s.lc(t) == sl["lc"], f"S-lc differs from mbfl.py: {key}"
        q_now = s.q(t)
        fail = np.abs(zP[:, t] - zR[:, t]) > EPS
        F = int(fail.sum())
        scores = defaultdict(float)
        for k, z in zM:
            kill = np.abs(z[:, t] - zP[:, t]) > EPS
            ef, ep = int((kill & fail).sum()), int((kill & ~fail).sum())
            scores[k] = max(scores[k], ef / np.sqrt(F * (ef + ep)) if F and (ef + ep) else 0.0)
        fault = set(u["fault"])
        row = u["meta"] | {"n_ops": len(P.data), "failing_tests": F, "q_recomputed_differs": int(q_now != sl["q"])}
        for name, univ in (("all", set(range(len(P.data)))),) + tuple(sl.items()):
            b, w, a = exam(scores, fault, sorted(univ))
            m = len(univ)
            f = len(fault & univ)
            # expected rank of the first of f fault instructions in a random order of m: (m + 1) / (f + 1)
            row |= {f"fault_in_{name}": int(f > 0), f"size_{name}": m, f"exam_{name}_best": b, f"exam_{name}_avg": a,
                    f"examined_{name}": round(b * m) if b is not None else None,
                    f"exam_{name}_random": ((m + 1) / (f + 1)) / m if f else None}
        rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    J = jobs(str(Path(a.data_root).resolve()))
    rows, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for i, f in enumerate(as_completed([ex.submit(_worker, j) for j in J]), 1):
            rows += f.result()
            if i % 40 == 0 or i == len(J):
                print(f"  {i}/{len(J)} circuits, {time.time() - t0:.0f}s", flush=True)
    rows.sort(key=lambda r: (r["source"], r["unit"]))
    with open(OUT / "units_all_rules.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)
    print(f"units {len(rows)}; wrote {OUT / 'units_all_rules.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
