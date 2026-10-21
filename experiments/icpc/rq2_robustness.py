"""RQ2 robustness of slices computed at |0...0> (PROTOCOL_ICPC.md section 3.2, H3).

The slice positions of S-q and S-lc are computed once, on the circuit as written, at |0...0>. Only
the input or the parameters then change, identically in the full circuit and the slice:
  R-basis  100 uniformly random computational-basis inputs (X gates prepended)
  R-haar   100 Haar-random product inputs (one U per qubit prepended)
  R-param  100 rebindings of every rotation angle of every top-level parameterized gate, uniform in
           [0, 2pi), same values in the full circuit and the slice; input |0...0>. Only circuits with
           at least one such angle. Composite gates defined in the QASM file keep their definition
           (their parameters are not rebound); the number of rebound angles is recorded.
Seed 20261021, one generator per regime and circuit (seeded by regime and circuit path).

Output (results/icpc/rq2_robustness/): pairs.csv, one row per (pair, slicer, regime) with the number of
sound draws; excluded.json.
Usage: python icpc/rq2_robustness.py --data-root DATA --eval-code ../selection --out OUT [--workers 12]
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

N_DRAWS, SEED = 100, 20261021
REGIMES = ["R-basis", "R-haar", "R-param"]
NOT_ROTATIONS = {"delay", "barrier", "measure", "reset", "unitary", "initialize", "if_else"}
# standard gates whose every parameter is an angle
ANGLE_GATES = {"rx", "ry", "rz", "p", "u", "u1", "u2", "u3", "cp", "cu1", "cu3", "cu", "crx", "cry", "crz",
               "rxx", "ryy", "rzz", "rzx", "r", "mcp", "cphase", "rv"}


def _rng(regime: str, path: str) -> np.random.Generator:
    h = int(hashlib.sha256(f"{SEED}:{regime}:{path}".encode()).hexdigest()[:12], 16)
    return np.random.default_rng(h)


def rebind(qc, rng):
    """Copy of qc with every angle of every top-level standard rotation gate redrawn in [0, 2pi)."""
    out = qc.copy_empty_like()
    n_angles = 0
    for inst in qc.data:
        op = inst.operation
        if op.name in ANGLE_GATES and op.params and all(isinstance(p, (int, float)) for p in op.params):
            op = op.to_mutable()
            op.params = [float(rng.uniform(0, 2 * np.pi)) for _ in op.params]
            n_angles += len(op.params)
        out.append(op, inst.qubits, inst.clbits)
    return out, n_angles


def n_rebindable(qc) -> int:
    return sum(len(i.operation.params) for i in qc.data if i.operation.name in ANGLE_GATES and i.operation.params
               and all(isinstance(p, (int, float)) for p in i.operation.params))


def _worker(job):
    corpus, name, rel, data_root = job
    from common.corpus import load
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from slicers.registry import Slicers

    t0 = time.time()
    qc = load(Path(data_root) / rel)
    n = qc.num_qubits
    s = Slicers(qc, name)
    slices = {(t, m): frozenset(s.get(m)(t)) for t in range(n) for m in ("q", "lc")}
    distinct = sorted(set(slices.values()), key=sorted)
    rows = []
    for regime in REGIMES:
        if regime == "R-param" and n_rebindable(qc) == 0:
            continue
        rng = _rng(regime, rel)
        sound = {k: 0 for k in slices}
        try:
            for _ in range(N_DRAWS):
                if regime == "R-param":
                    full_c, _ = rebind(qc, rng)
                    prep = None
                else:
                    full_c = qc
                    prep = oi.basis_input(n, rng) if regime == "R-basis" else oi.haar_product_input(n, rng)
                base = oi.reduced_states(oi.with_input(full_c, prep), range(n))
                states = {sl: oi.reduced_states(oi.with_input(materialise(full_c, sl), prep), range(n)) for sl in distinct}
                for (t, m), sl in slices.items():
                    if oi.uhlmann_fidelity(base[t], states[sl][t]) >= 1 - oi.FIDELITY_EPS:
                        sound[(t, m)] += 1
        except oi.OracleError as exc:
            return {"excluded": f"oracle ({regime}): {exc}", "corpus": corpus, "circuit": name, "path": rel}
        for (t, m), cnt in sound.items():
            rows.append({"corpus": corpus, "circuit": name, "path": rel, "n_qubits": n, "n_ops": len(qc.data),
                         "dynamic": int(any(i.operation.name in ("measure", "reset", "if_else") for i in qc.data)),
                         "target": t, "slicer": m, "regime": regime, "draws": N_DRAWS, "sound_draws": cnt,
                         "robust": int(cnt == N_DRAWS), "pruned": int(slices[(t, "q")] != slices[(t, "lc")]),
                         "n_rebindable_angles": n_rebindable(qc)})
    return {"rows": rows, "seconds": time.time() - t0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--eval-code", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--limit", type=int, default=None, help="debug only: first N circuits")
    a = ap.parse_args()
    from common.corpus import corpus_a
    root, out = Path(a.data_root).resolve(), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    A = corpus_a(root, Path(a.eval_code))
    excluded = [{"corpus": e.corpus, "circuit": e.name, "path": e.path, "reason": f"load: {e.error}"} for e in A if e.qc is None]
    sizes = {e.path: len(e.qc.data) * e.qc.num_qubits for e in A if e.qc is not None}
    # --limit takes the first N circuits in corpus order (the same debug circuits as icpc/rq1_run.py)
    jobs = sorted([(e.corpus, e.name, e.path, str(root)) for e in A if e.qc is not None][: a.limit], key=lambda j: -sizes[j[2]])
    rows, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for i, res in enumerate(ex.map(_worker, jobs, chunksize=1), 1):
            if "excluded" in res:
                excluded.append({k: res[k] for k in ("corpus", "circuit", "path")} | {"reason": res["excluded"]})
            else:
                rows += res["rows"]
            if i % 10 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} circuits, {time.time() - t0:.0f}s", flush=True)
    rows.sort(key=lambda r: (r["path"], r["target"], r["slicer"], r["regime"]))
    with open(out / "pairs.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (out / "excluded.json").write_text(json.dumps(excluded, indent=2))
    print(f"rows: {len(rows)}; excluded: {len(excluded)}; wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
