"""S-lcq with an order-aligned mapping (Deviation I-9): Qiskit's LightCone on every RQ1 pair, mapped back to
instruction positions without relying on labels alone.

slicers/registry.py::_lightcone labels every instruction and reads the labels back. LightCone returns
copies of gates defined in the QASM file itself (qasm2 `_DefinedGate`: mcx, qft, oracles, ...) without
their labels, so the RQ1 run recorded those pairs as "not applicable". The pass keeps an in-order
subsequence of the input: it walks the DAG in reverse topological order and re-applies each kept node at
the front, and a loaded circuit's topological order is its instruction order. Here the output is
aligned to the input in order. A labelled instruction anchors to its position. An unlabelled one is
matched to an input instruction with the same name, qubits, clbits and parameters, between the
neighbouring anchors. The alignment is computed earliest-first and latest-first. If the two differ
(identical gates where one was dropped), the pair is recorded as "ambiguous" and not applicable.
LightCone's own refusals (measurements with an observable) stay not applicable, as pre-registered.
Scoring is that of icpc/rq1_run.py: soundness under the oracle at |0...0>, dependence recall and
precision against the semantic-dependence ground truth.
Outputs (results/icpc/rq1_lcq_remap/): records.csv (slicers lcq and lcq_z), excluded.json.
Usage (from experiments/): python icpc/lcq_remap.py --data-root ../data --eval-code ../selection [--workers 6]
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
OUT = HERE / "results" / "icpc" / "rq1_lcq_remap"
PAULIS = {"lcq": ("X", "Y", "Z"), "lcq_z": ("Z",)}


class NotApplicable(Exception):
    pass


def _sig(qc, inst):
    return (inst.operation.name, tuple(qc.find_bit(q).index for q in inst.qubits),
            tuple(qc.find_bit(c).index for c in inst.clbits), tuple(str(p) for p in inst.operation.params))


def _align(src_sigs, out, reverse: bool):
    """Map each output (label_k or None, sig) to an input position; None if no consistent match."""
    m, n = len(out), len(src_sigs)
    pos = [None] * m
    anchors = [(j, k) for j, (k, _) in enumerate(out) if k is not None]
    if any(src_sigs[k] != out[j][1] for j, k in anchors):
        return None
    order = range(m - 1, -1, -1) if reverse else range(m)
    for j, k in anchors:
        pos[j] = k
    for j in order:
        if pos[j] is not None:
            continue
        lo = max([pos[i] for i in range(j) if pos[i] is not None], default=-1) + 1
        hi = min([pos[i] for i in range(j + 1, m) if pos[i] is not None], default=n)
        cand = [k for k in range(lo, hi) if src_sigs[k] == out[j][1]]
        if not cand:
            return None
        pos[j] = cand[-1] if reverse else cand[0]
    return pos


def lightcone_positions(qc, t: int, paulis) -> set:
    from qiskit.transpiler import PassManager
    from qiskit.transpiler.passes import LightCone
    labelled = qc.copy_empty_like()
    for k, inst in enumerate(qc.data):
        op = inst.operation.to_mutable()
        op.label = f"__k{k}"
        labelled.append(op, inst.qubits, inst.clbits)
    src_sigs = [_sig(qc, inst) for inst in qc.data]
    keep = set()
    for p in paulis:
        try:
            res = PassManager([LightCone(bit_terms=p, indices=[t])]).run(labelled)
        except Exception as exc:
            raise NotApplicable(f"LightCone({p}): {type(exc).__name__}: {exc}") from exc
        out = []
        for inst in res.data:
            lab = getattr(inst.operation, "label", None) or ""
            out.append((int(lab[3:]) if lab.startswith("__k") else None, _sig(res, inst)))
        first, last = _align(src_sigs, out, False), _align(src_sigs, out, True)
        if first is None or last is None:
            raise NotApplicable(f"LightCone({p}): output is not an in-order subsequence of the input")
        if first != last:
            raise NotApplicable(f"LightCone({p}): ambiguous alignment")
        keep |= set(first)
    return keep


def _worker(job):
    corpus, name, rel, data_root = job
    from common.corpus import load
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    from icpc.influence import influence, influence_sets
    t0 = time.time()
    qc = load(Path(data_root) / rel)
    n, nops = qc.num_qubits, len(qc.data)
    dynamic = any(i.operation.name in ("measure", "reset", "if_else") for i in qc.data)
    try:
        base = oi.reduced_states(qc, range(n))
        inf_by_q = influence_sets(influence(qc), n)
    except oi.OracleError as exc:
        return {"excluded": f"oracle: {exc}", "corpus": corpus, "circuit": name, "path": rel}
    unlabelled = any(i.operation.name not in ("measure", "reset", "barrier") and type(i.operation).__name__ == "_DefinedGate"
                     for i in qc.data)
    recs, cache = [], {}
    for t in range(n):
        inf = inf_by_q[t]
        for m, paulis in PAULIS.items():
            row = {"corpus": corpus, "circuit": name, "path": rel, "n_qubits": n, "n_ops": nops,
                   "dynamic": int(dynamic), "target": t, "slicer": m, "has_defined_gate": int(unlabelled)}
            try:
                sl = lightcone_positions(qc, t, paulis)
            except NotApplicable as exc:
                recs.append(row | {"applicable": 0, "note": str(exc)[:200]})
                continue
            key = frozenset(sl)
            if key not in cache:
                cache[key] = oi.reduced_states(materialise(qc, key), range(n))
            f = oi.uhlmann_fidelity(base[t], cache[key][t])
            hit = len(sl & inf)
            recs.append(row | {"applicable": 1, "note": "", "size": len(sl), "size_fraction": len(sl) / max(nops, 1),
                               "fidelity": f, "sound": int(f >= 1 - oi.FIDELITY_EPS), "n_influencing": len(inf),
                               "dep_recall": hit / len(inf) if inf else 1.0,
                               "dep_precision": hit / len(sl) if sl else 1.0,
                               "n_missed": len(inf - sl), "n_non_influencing": len(sl - inf),
                               "slice": ";".join(map(str, sorted(sl)))})
    return {"recs": recs, "seconds": time.time() - t0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--eval-code", default="../selection")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    from common.corpus import corpus_a
    root = Path(a.data_root).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    A = corpus_a(root, Path(a.eval_code))
    excluded = [{"corpus": e.corpus, "circuit": e.name, "path": e.path, "reason": f"load: {e.error}"} for e in A if e.qc is None]
    jobs = [(e.corpus, e.name, e.path, str(root)) for e in A if e.qc is not None]
    recs, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(_worker, j) for j in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            res = f.result()
            if "excluded" in res:
                excluded.append({k: res[k] for k in ("corpus", "circuit", "path")} | {"reason": res["excluded"]})
            else:
                recs += res["recs"]
            if i % 20 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} circuits, {time.time() - t0:.0f}s", flush=True)
    recs.sort(key=lambda r: (r["path"], r["target"], r["slicer"]))
    with open(OUT / "records.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in recs for k in r)))
        w.writeheader()
        w.writerows(recs)
    (OUT / "excluded.json").write_text(json.dumps(excluded, indent=2))
    lcq = [r for r in recs if r["slicer"] == "lcq"]
    print(f"lcq applicable {sum(r['applicable'] for r in lcq)}/{len(lcq)}; "
          f"unsound {sum(r['applicable'] and not r['sound'] for r in lcq)}; wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
