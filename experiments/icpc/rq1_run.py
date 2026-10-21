"""RQ1 on corpus A (PROTOCOL_ICPC.md section 2, 2.1; Deviation I-1).

Per (circuit, criterion qubit):
  - slices of du, lc, lcq, lcq_z, yz, q, 4e_unfixed, 4e_fixed, and qW with W = {t}; soundness under the
    oracle at |0...0> (fidelity >= 1 - 1e-6);
  - the semantic-dependence ground truth (icpc/influence.py) and the as-written contribution;
  - dependence recall and precision per slicer; every missed influencing instruction classified by the
    fixed structural rule (same-wire, feedback, written-operand, kickback);
  - LightCone agreement (lcq == lc), and the check qW({t}) == q.

Outputs (results/icpc/rq1/): records.csv (one row per pair x slicer), misses.csv (one row per missed
dependence), pairs.csv (one row per pair), excluded.json.
Usage: python icpc/rq1_run.py --data-root DATA --eval-code ../selection --out results/icpc/rq1 [--workers 6]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from qiskit import ClassicalRegister

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

SLICERS = ["du", "lc", "lcq", "lcq_z", "yz", "q", "4e_unfixed", "4e_fixed", "qW"]


def _writes(op, inst_qubits, q_index, q) -> bool:
    """Does the instruction write qubit q under the def-use port's rule?"""
    qs = [q_index[x] for x in inst_qubits]
    nc = int(getattr(op, "num_ctrl_qubits", 0) or 0)
    if nc and len(qs) > nc:
        return q in qs[nc:]
    return q in qs


def classify_miss(qc, k: int, q: int) -> str:
    """Category of an influencing instruction k outside a slice for criterion q (section 2.1)."""
    q_index = {b: i for i, b in enumerate(qc.qubits)}
    data = qc.data
    on = [{q_index[b] for b in inst.qubits} for inst in data]
    if q in on[k]:
        return "same-wire"
    # successor edges: DATA (next instruction on each wire) and CONTROL (measurement -> conditions
    # reading its bit before the bit is next written)
    data_succ = {i: set() for i in range(len(data))}
    for i in range(len(data)):
        for w in on[i]:
            for j in range(i + 1, len(data)):
                if w in on[j]:
                    data_succ[i].add(j)
                    break
    ctrl_succ = {i: set() for i in range(len(data))}
    for i, inst in enumerate(data):
        if inst.operation.name == "measure":
            bit = inst.clbits[0]
            for j in range(i + 1, len(data)):
                op = data[j].operation
                if op.name == "if_else":
                    tgt = op.condition[0]
                    # a QASM 2 `if(creg==v)` condition is a register; it has no __iter__ attribute
                    bits = list(tgt) if isinstance(tgt, ClassicalRegister) else [tgt]
                    if bit in bits:
                        ctrl_succ[i].add(j)
                if op.name == "measure" and bit in data[j].clbits:
                    break

    def entries(use_control: bool):
        seen, out, dq = {k}, set(), deque([k])
        while dq:
            x = dq.popleft()
            for y in data_succ[x] | (ctrl_succ[x] if use_control else set()):
                if y in seen:
                    continue
                seen.add(y)
                if q in on[y]:
                    out.add(y)
                else:
                    dq.append(y)
        return out

    data_only, everything = entries(False), entries(True)
    if not everything:
        return "unreachable"  # would contradict no-signalling; reported if it ever occurs
    if not data_only:
        return "feedback"
    if any(_writes(data[e].operation, data[e].qubits, q_index, q) for e in everything):
        return "written-operand"
    return "kickback"


def _worker(job):
    corpus, name, rel, data_root = job
    from common.corpus import load
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from icpc.influence import contribution, influence, influence_sets
    from slicers.registry import NotApplicable, Slicers, qslice_set

    t0 = time.time()
    qc = load(Path(data_root) / rel)
    n, nops = qc.num_qubits, len(qc.data)
    dynamic = any(i.operation.name in ("measure", "reset", "if_else") for i in qc.data)
    try:
        base = oi.reduced_states(qc, range(n))
        inf_by_q = influence_sets(influence(qc), n)
        con = contribution(qc)
    except oi.OracleError as exc:
        return {"excluded": f"oracle: {exc}", "corpus": corpus, "circuit": name, "path": rel}
    s = Slicers(qc, name)
    recs, misses, pairs, cache = [], [], [], {}
    for t in range(n):
        inf = inf_by_q[t]
        contrib_zero = {k for k, v in con.items() if t in v["zero"]}
        contrib_any = {k for k, v in con.items() if t in v["any"]}
        slices = {}
        for m in SLICERS:
            try:
                slices[m] = qslice_set(qc, [t], slicers=s) if m == "qW" else s.get(m)(t)
            except NotApplicable as exc:
                slices[m] = None
                recs.append({"corpus": corpus, "circuit": name, "path": rel, "n_qubits": n, "n_ops": nops,
                             "dynamic": int(dynamic), "target": t, "slicer": m, "applicable": 0, "note": str(exc)[:200]})
        for m, sl in slices.items():
            if sl is None:
                continue
            key = frozenset(sl)
            if key not in cache:
                cache[key] = oi.reduced_states(materialise(qc, key), range(n))
            f = oi.uhlmann_fidelity(base[t], cache[key][t])
            hit = len(sl & inf)
            recs.append({"corpus": corpus, "circuit": name, "path": rel, "n_qubits": n, "n_ops": nops,
                         "dynamic": int(dynamic), "target": t, "slicer": m, "applicable": 1, "note": "",
                         "size": len(sl), "size_fraction": len(sl) / max(nops, 1), "fidelity": f,
                         "sound": int(f >= 1 - oi.FIDELITY_EPS), "n_influencing": len(inf),
                         "dep_recall": hit / len(inf) if inf else 1.0,
                         "dep_precision": hit / len(sl) if sl else 1.0,
                         "n_missed": len(inf - sl), "n_non_influencing": len(sl - inf)})
            if m in ("du", "lc", "lcq", "yz", "q", "4e_fixed"):
                for k in sorted(inf - sl):
                    misses.append({"corpus": corpus, "circuit": name, "path": rel, "target": t, "slicer": m,
                                   "position": k, "gate": qc.data[k].operation.name,
                                   "category": classify_miss(qc, k, t)})
        lc, q = slices["lc"], slices["q"]
        removed = lc - q
        pairs.append({"corpus": corpus, "circuit": name, "path": rel, "n_qubits": n, "n_ops": nops,
                      "dynamic": int(dynamic), "target": t, "n_influencing": len(inf),
                      "lcq_equals_lc": "" if slices["lcq"] is None else int(slices["lcq"] == lc),
                      "qW_equals_q": int(slices["qW"] == q),
                      "q_pruned": int(bool(removed)), "q_removed": len(removed),
                      # Deviation I-1 item 3: classification of each S-q prune
                      "removed_non_influencing": len(removed - inf),
                      "removed_influencing_no_contribution": len((removed & inf) - contrib_any),
                      "removed_influencing_contributing_some_input": len(removed & inf & contrib_any),
                      "removed_contributing_at_zero": len(removed & contrib_zero),
                      "lc_non_influencing": len(lc - inf)})
    return {"recs": recs, "misses": misses, "pairs": pairs, "seconds": time.time() - t0}


def _write(path: Path, rows):
    if not rows:
        path.write_text("")
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--eval-code", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=None, help="debug only: first N circuits")
    a = ap.parse_args()
    from common.corpus import corpus_a
    root, out = Path(a.data_root).resolve(), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    A = corpus_a(root, Path(a.eval_code))
    excluded = [{"corpus": e.corpus, "circuit": e.name, "path": e.path, "reason": f"load: {e.error}"} for e in A if e.qc is None]
    jobs = [(e.corpus, e.name, e.path, str(root)) for e in A if e.qc is not None][: a.limit]
    # largest circuits first so the pool finishes evenly
    jobs.sort(key=lambda j: -next(len(e.qc.data) * e.qc.num_qubits for e in A if e.path == j[2]))
    recs, misses, pairs, t0 = [], [], [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for i, res in enumerate(ex.map(_worker, jobs, chunksize=1), 1):
            if "excluded" in res:
                excluded.append({k: res[k] for k in ("corpus", "circuit", "path")} | {"reason": res["excluded"]})
            else:
                recs += res["recs"]; misses += res["misses"]; pairs += res["pairs"]
            if i % 10 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} circuits, {time.time() - t0:.0f}s", flush=True)
    key = lambda r: (r["path"], r["target"])  # noqa: E731
    recs.sort(key=lambda r: (r["path"], r["target"], SLICERS.index(r["slicer"])))
    misses.sort(key=lambda r: (r["path"], r["target"], r["slicer"], r["position"]))
    pairs.sort(key=key)
    _write(out / "records.csv", recs)
    _write(out / "misses.csv", misses)
    _write(out / "pairs.csv", pairs)
    (out / "excluded.json").write_text(json.dumps(excluded, indent=2))
    print(f"pairs: {len(pairs)}; excluded circuits: {len(excluded)}; wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
