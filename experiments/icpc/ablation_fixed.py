"""Four-edge fix on the ablation (PROTOCOL_ICPC.md section 2; Deviation I-1 item 4): the edge-type ablation
of rq4_ablation_rerun/run.py re-run with the measured-criterion fix.

Every variant (QSlice-full, QDG-no-ED, QDG-no-MD, QDG-no-UED, QDG-no-CD, Classical PDG, Causal-cone) keeps its
edge types and graph. Only the seed changes. The unfixed slicer seeds the backward slice at the criterion's
measurement node; the fixed one seeds it at the criterion qubit's last operation of any kind, exactly as
slicers/registry.py::four_fixed does for QSlice-full. Corpora, oracle, soundness rule, summary table and
McNemar tests are those of rq4_ablation_rerun/run.py, unchanged; the unfixed results are results/rq4_ablation.
Outputs (results/icpc/ablation_fixed/): records.csv, excluded.json, TAB_ablation_rerun.csv, tests.json.
Usage (from experiments/): python icpc/ablation_fixed.py --data-root ../data --eval-code ../selection
                           --four-edge ../fouredge [--workers 8]
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
from rq4_ablation_rerun.run import FIELDS, VARIANTS, summarise  # noqa: E402

OUT = HERE / "results" / "icpc" / "ablation_fixed"


def fixed_slice(g, t: int, enabled) -> frozenset:
    """Backward reachability over edges of the enabled types, seeded at t's last operation."""
    on_t = [gid for gid, node in g.nodes.items() if t in node.qubits]
    if not on_t:
        return frozenset()
    preds: dict = {}
    for u, v, data in g.graph.edges(data=True):
        if data.get("types", set()) & enabled:
            preds.setdefault(v, []).append(u)
    seen, stack = set(), [max(on_t)]
    while stack:
        x = stack.pop()
        if x in seen:
            continue
        seen.add(x)
        stack.extend(preds.get(x, []))
    return frozenset(seen)


def _worker(job):
    corpus, name, rel, data_root, four_edge = job
    sys.path.insert(0, four_edge)
    from common.corpus import load
    from common.evaluate import FIDELITY_EPS, materialise
    from common.oracle import OracleError, fidelity, reduced_states, trace_distance
    from src.qdg import qdg_from_circuit
    from src.slicer import SlicerVariant, VARIANT_EDGE_TYPES

    qc = load(Path(data_root) / rel)
    n, nops = qc.num_qubits, len(qc.data)
    dynamic = any(i.operation.name in ("measure", "reset", "if_else") for i in qc.data)
    try:
        full = reduced_states(qc, range(n))
    except OracleError as exc:
        return {"excluded": f"oracle: {exc}", "corpus": corpus, "circuit": name, "path": rel}
    qdg = qdg_from_circuit(qc, name)
    cache, rows = {}, []
    for t in range(n):
        for v in VARIANTS:
            ids = fixed_slice(qdg, t, VARIANT_EDGE_TYPES[SlicerVariant(v)])
            if ids not in cache:
                try:
                    cache[ids] = reduced_states(materialise(qc, ids), range(n))
                except OracleError as exc:
                    return {"excluded": f"oracle on slice: {exc}", "corpus": corpus, "circuit": name, "path": rel}
            rho = cache[ids][t]
            f = fidelity(full[t], rho)
            rows.append({"corpus": corpus, "circuit": name, "path": rel, "n_qubits": n, "n_ops": nops,
                         "dynamic": int(dynamic), "target": t, "variant": v,
                         "slice_size_fraction": len(ids) / max(nops, 1), "fidelity": f,
                         "trace_distance": trace_distance(full[t], rho), "sound": int(f >= 1 - FIDELITY_EPS)})
    return {"rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--eval-code", required=True)
    ap.add_argument("--four-edge", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None, help="debug only: first N circuits")
    a = ap.parse_args()
    from common.corpus import corpus_a, corpus_b
    root = Path(a.data_root).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    A = corpus_a(root, Path(a.eval_code))
    B = corpus_b(root, {e.path for e in A})
    entries = A + B
    excluded = [{"corpus": e.corpus, "circuit": e.name, "path": e.path, "reason": f"load: {e.error}"}
                for e in entries if e.qc is None]
    jobs = [(e.corpus, e.name, e.path, str(root), str(Path(a.four_edge).resolve()))
            for e in entries if e.qc is not None][: a.limit]
    t0, rows = time.time(), []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for i, res in enumerate(ex.map(_worker, jobs, chunksize=1), 1):
            if "excluded" in res:
                excluded.append({k: res[k] for k in ("corpus", "circuit", "path")} | {"reason": res["excluded"]})
            else:
                rows.extend(res["rows"])
            if i % 10 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} circuits, {time.time() - t0:.0f}s", flush=True)
    with open(OUT / "records.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    (OUT / "excluded.json").write_text(json.dumps(excluded, indent=2))
    table = summarise(rows, OUT)
    for r in table:
        if r["unit"] == "pair" and r["scope"] == "A+B":
            print(f"  {r['variant']:15s} SVR {r['svr']:.4f}  dSVR {r['delta_svr']}  (n={r['n']} pairs)")
    print(f"excluded circuits: {len(excluded)}; wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
