"""A flow-sensitive reading of Yu & Zhao's QPDG (Deviation I-16, exploratory).

S-yzf (slicers/yuzhao.py::yuzhao_flow_graph) is S-yz with entanglement counted only from the two-qubit gate
that couples two qubits on. Per corpus-A circuit and criterion qubit, S-yzf and S-yz (recomputed, as a check
against results/icpc/rq1/records.csv) are scored as in RQ1: soundness at |0...0>, dependence recall and
precision against the influence ground truth (icpc/influence.py), size.
--part families / catalogue: soundness of S-yzf and S-yz at |0...0>.
Output: results/icpc/yz_flow/ (records.csv, excluded.json, families.csv, catalogue.csv).
Usage (from experiments/): python icpc/yz_flow.py --part corpus-a --data-root ../data --eval-code ../selection [--workers 6]
                           python icpc/yz_flow.py --part families | catalogue
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
OUT = HERE / "results" / "icpc" / "yz_flow"


def _slices(qc, name):
    from slicers.registry import Slicers
    from slicers.yuzhao import yuzhao_flow_graph
    s = Slicers(qc, name)
    g = yuzhao_flow_graph(qc, HERE)
    out = {}
    for t in range(qc.num_qubits):
        out[(t, "lc")] = frozenset(s.lc(t))
        out[(t, "yz")] = frozenset(s.yz(t))
        out[(t, "yzf")] = frozenset(g.backward_slice(t))
    return out


def _worker(job):
    corpus, name, rel, data_root = job
    from common.corpus import load
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from icpc.influence import influence, influence_sets

    t0 = time.time()
    qc = load(Path(data_root) / rel)
    n, nops = qc.num_qubits, len(qc.data)
    dyn = int(any(i.operation.name in ("measure", "reset", "if_else") for i in qc.data))
    try:
        base = oi.reduced_states(qc, range(n))
        dep = influence_sets(influence(qc), n)
    except oi.OracleError as exc:
        return {"excluded": f"oracle: {exc}", "corpus": corpus, "circuit": name, "path": rel}
    sl = _slices(qc, name)
    common = {"corpus": corpus, "circuit": name, "path": rel, "n_qubits": n, "n_ops": nops, "dynamic": dyn}
    recs, cache = [], {}
    for t in range(n):
        for m in ("yz", "yzf"):
            x = sl[(t, m)]
            if x not in cache:
                cache[x] = oi.reduced_states(materialise(qc, x), range(n))
            f = oi.uhlmann_fidelity(base[t], cache[x][t])
            hit = len(x & dep[t])
            recs.append(common | {"target": t, "slicer": m, "size": len(x), "size_fraction": len(x) / max(nops, 1),
                                  "fidelity": f, "sound": int(f >= 1 - oi.FIDELITY_EPS), "n_influencing": len(dep[t]),
                                  "dep_recall": hit / len(dep[t]) if dep[t] else 1.0,
                                  "dep_precision": hit / len(x) if x else 1.0,
                                  "contains_lc": int(sl[(t, "lc")] <= x), "within_yz": int(x <= sl[(t, "yz")]),
                                  "slice": ";".join(map(str, sorted(x)))})
    return {"recs": recs, "seconds": time.time() - t0}


def _write(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)


def corpus_a(a) -> int:
    from common.corpus import corpus_a as load_a
    root = Path(a.data_root).resolve()
    A = load_a(root, Path(a.eval_code))
    excluded = [{"corpus": e.corpus, "circuit": e.name, "path": e.path, "reason": f"load: {e.error}"} for e in A if e.qc is None]
    sizes = {e.path: len(e.qc.data) * e.qc.num_qubits for e in A if e.qc is not None}
    jobs = sorted([(e.corpus, e.name, e.path, str(root)) for e in A if e.qc is not None], key=lambda j: -sizes[j[2]])
    recs, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(_worker, j) for j in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            res = f.result()
            if "excluded" in res:
                excluded.append({k: res[k] for k in ("corpus", "circuit", "path")} | {"reason": res["excluded"]})
            else:
                recs += res["recs"]
            if i % 10 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} circuits, {time.time() - t0:.0f}s", flush=True)
    _write(OUT / "records.csv", sorted(recs, key=lambda r: (r["path"], r["target"], r["slicer"])))
    (OUT / "excluded.json").write_text(json.dumps(excluded, indent=2))
    s = [r for r in recs if r["slicer"] == "yzf"]
    print(f"yzf pairs {len(s)}; unsound {sum(not r['sound'] for r in s)}; "
          f"contains wire {sum(r['contains_lc'] for r in s)}; within yz {sum(r['within_yz'] for r in s)}; wrote {OUT}")
    return 0


def small(part: str) -> int:
    """Soundness of S-yzf and S-yz at |0...0> on the structure families or the dependence catalogue."""
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    if part == "families":
        from families.generate import families
        items = [(f"{f}:{n}", c, None) for f, n, c in families()]
    else:
        from tests.dependence_catalogue import CATALOGUE
        items = [(kid, build(), t) for kid, kind, build, t, exp in CATALOGUE]
    rows = []
    for name, qc, only in items:
        base = oi.reduced_states(qc, range(qc.num_qubits))
        sl = _slices(qc, name)
        for t in ([only] if only is not None else range(qc.num_qubits)):
            for m in ("yz", "yzf"):
                x = sl[(t, m)]
                f = oi.uhlmann_fidelity(base[t], oi.reduced_states(materialise(qc, x), [t])[t])
                rows.append({"circuit": name, "target": t, "slicer": m, "size": len(x), "n_ops": len(qc.data),
                             "fidelity": f, "sound": int(f >= 1 - oi.FIDELITY_EPS)})
    _write(OUT / f"{part}.csv", rows)
    for m in ("yz", "yzf"):
        r = [x for x in rows if x["slicer"] == m]
        print(f"{part} {m}: {len(r)} pairs, unsound {sum(not x['sound'] for x in r)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["corpus-a", "families", "catalogue"], required=True)
    ap.add_argument("--data-root")
    ap.add_argument("--eval-code", default="../selection")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    return corpus_a(a) if a.part == "corpus-a" else small(a.part)


if __name__ == "__main__":
    sys.exit(main())
