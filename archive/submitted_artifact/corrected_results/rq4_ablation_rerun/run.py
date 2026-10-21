"""RQ4 edge-type ablation, re-run under the pre-registered protocol (../PROTOCOL.md, section 2).

Slicers: the unchanged four-edge implementation (reported_results/rq4_ablation/src), variants
QSlice-full, QDG-no-ED, QDG-no-MD, QDG-no-UED, QDG-no-CD, plus Classical PDG and Causal-cone for
context. Every (circuit, criterion qubit) pair of corpora A and B is sliced by every variant and judged
by the exact oracle (common/oracle.py): sound iff fidelity of the criterion's reduced state >= 1 - 1e-6.

Usage: python run.py --data-root DATA --eval-code EVAL_CODE --four-edge FOUR_EDGE --out OUT [--workers N]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

VARIANTS = ["QSlice-full", "QDG-no-ED", "QDG-no-MD", "QDG-no-UED", "QDG-no-CD", "Classical PDG", "Causal-cone"]
ABLATED = {"QDG-no-ED": "ED (entanglement)", "QDG-no-MD": "MD (measurement-collapse)",
           "QDG-no-UED": "UED (unitary-evolution)", "QDG-no-CD": "CD (classical-feedback)"}
FIELDS = ["corpus", "circuit", "path", "n_qubits", "n_ops", "dynamic", "target", "variant",
          "slice_size_fraction", "fidelity", "trace_distance", "sound"]


def _worker(job):
    corpus, name, rel, data_root, four_edge = job
    sys.path.insert(0, four_edge)
    from common.corpus import load
    from common.evaluate import FIDELITY_EPS, materialise
    from common.oracle import OracleError, fidelity, reduced_states, trace_distance
    from src.qdg import qdg_from_circuit
    from src.slicer import SlicerVariant, VARIANT_EDGE_TYPES
    from src.qdg import slice_from_qdg

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
            ids = frozenset(slice_from_qdg(qdg, t, VARIANT_EDGE_TYPES[SlicerVariant(v)]))
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


def summarise(rows, out: Path):
    from common.evaluate import mcnemar_exact, rate
    scopes = {"A": lambda r: r["corpus"] != "VeriQBench-dynamic",
              "B": lambda r: r["corpus"] == "VeriQBench-dynamic",
              "A+B": lambda r: True,
              "dynamic circuits in A+B": lambda r: r["dynamic"] == 1}
    table, tests = [], {}
    for scope, keep in scopes.items():
        sub = [r for r in rows if keep(r)]
        pairs = sorted({(r["path"], r["target"]) for r in sub})
        circuits = sorted({r["path"] for r in sub})
        viol = {v: {(r["path"], r["target"]): not r["sound"] for r in sub if r["variant"] == v} for v in VARIANTS}
        for unit, keys in (("pair", pairs), ("circuit", circuits)):
            def svr(v):
                if unit == "pair":
                    return rate([viol[v][k] for k in keys])
                return rate([any(viol[v][(c, t)] for (c, t) in pairs if c == k) for k in keys])
            base = svr("QSlice-full")
            for v in VARIANTS:
                s = svr(v)
                table.append({"scope": scope, "unit": unit, "n": len(keys), "variant": v,
                              "removed_edge_type": ABLATED.get(v, ""), "svr": round(s, 4),
                              "delta_svr": round(s - base, 4) if v in ABLATED else ""})
        tests[scope] = {v: mcnemar_exact([viol[v][k] for k in pairs], [viol["QSlice-full"][k] for k in pairs])
                        for v in ABLATED}
    with open(out / "TAB_ablation_rerun.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    (out / "tests.json").write_text(json.dumps(tests, indent=2))
    return table


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--eval-code", required=True)
    ap.add_argument("--four-edge", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None, help="debug only: first N circuits")
    a = ap.parse_args()
    from common.corpus import corpus_a, corpus_b
    root, out = Path(a.data_root), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
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
            if i % 10 == 0:
                print(f"  {i}/{len(jobs)} circuits, {time.time() - t0:.0f}s", flush=True)
    with open(out / "records.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    (out / "excluded.json").write_text(json.dumps(excluded, indent=2))
    table = summarise(rows, out)
    for r in table:
        if r["unit"] == "pair" and r["scope"] == "A+B":
            print(f"  {r['variant']:15s} SVR {r['svr']:.4f}  dSVR {r['delta_svr']}  (n={r['n']} pairs)")
    print(f"excluded circuits: {len(excluded)}; wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
