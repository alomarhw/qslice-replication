"""RQ2 robustness of S-lcq (Deviation I-10): icpc/rq2_robustness.py with Qiskit's LightCone as the slicer.

Regimes, draws, seeds and the soundness rule are those of icpc/rq2_robustness.py, imported unchanged, so
every draw is identical to the RQ2 run. S-lcq positions come from icpc/lcq_remap.py (Deviation I-9) and,
like S-lc and S-q in RQ2, are computed once on the circuit as written, at |0...0>. S-lc is run again
on the same draws as a reproduction check: its sound-draw counts must equal results/icpc/rq2_robustness.
Pairs where S-lcq is not applicable are recorded with applicable = 0.
Output (results/icpc/rq2_robustness_lcq/): pairs.csv, excluded.json.
Usage (from experiments/): python icpc/rq2_robustness_lcq.py --data-root ../data --eval-code ../selection [--workers 8]
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
from icpc.rq2_robustness import N_DRAWS, REGIMES, _rng, n_rebindable, rebind  # noqa: E402

OUT = HERE / "results" / "icpc" / "rq2_robustness_lcq"


def _worker(job):
    corpus, name, rel, data_root = job
    from common.corpus import load
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from icpc.lcq_remap import NotApplicable, lightcone_positions
    from slicers.registry import Slicers

    t0 = time.time()
    qc = load(Path(data_root) / rel)
    n = qc.num_qubits
    s = Slicers(qc, name)
    slices, na = {}, {}
    for t in range(n):
        slices[(t, "lc")] = frozenset(s.lc(t))
        try:
            slices[(t, "lcq")] = frozenset(lightcone_positions(qc, t, ("X", "Y", "Z")))
        except NotApplicable as exc:
            na[t] = str(exc)[:200]
    distinct = sorted(set(slices.values()), key=sorted)
    dyn = int(any(i.operation.name in ("measure", "reset", "if_else") for i in qc.data))
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
        common = {"corpus": corpus, "circuit": name, "path": rel, "n_qubits": n, "n_ops": len(qc.data), "dynamic": dyn,
                  "regime": regime, "draws": N_DRAWS, "n_rebindable_angles": n_rebindable(qc)}
        for t in range(n):
            for m in ("lc", "lcq"):
                if (t, m) not in slices:
                    rows.append(common | {"target": t, "slicer": m, "applicable": 0, "note": na[t]})
                    continue
                cnt = sound[(t, m)]
                rows.append(common | {"target": t, "slicer": m, "applicable": 1, "note": "", "sound_draws": cnt,
                                      "robust": int(cnt == N_DRAWS), "size": len(slices[(t, m)]),
                                      "lcq_smaller_than_lc": int(m == "lcq" and slices[(t, m)] < slices[(t, "lc")])})
    return {"rows": rows, "seconds": time.time() - t0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--eval-code", required=True)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    from common.corpus import corpus_a
    root = Path(a.data_root).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    A = corpus_a(root, Path(a.eval_code))
    excluded = [{"corpus": e.corpus, "circuit": e.name, "path": e.path, "reason": f"load: {e.error}"} for e in A if e.qc is None]
    sizes = {e.path: len(e.qc.data) * e.qc.num_qubits for e in A if e.qc is not None}
    jobs = sorted([(e.corpus, e.name, e.path, str(root)) for e in A if e.qc is not None], key=lambda j: -sizes[j[2]])
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
    with open(OUT / "pairs.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)
    (OUT / "excluded.json").write_text(json.dumps(excluded, indent=2))
    print(f"rows: {len(rows)}; excluded: {len(excluded)}; wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
