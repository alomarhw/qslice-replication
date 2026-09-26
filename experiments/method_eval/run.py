"""RQ1-RQ3 with the method described in Sec. III, under the pre-registered protocol (../PROTOCOL.md,
section 3).

Slicers, all from the unchanged method prototype (described_method/qdg.py, QDG built with data,
control and entanglement edges):
  qpdg   = QDG.entanglement_pruned_slice(t)          (Sec. III: causal cone + MI pruning + check)
  naive  = QDG.naive_classical_backward_slice(t)      (classical def-use port)
  causal = QDG without entanglement edges, backward_slice(t)
Forward slices: QDG.forward_slice, naive_classical_forward_slice, causal forward_slice.

Corpus A (the paper's 161 circuits, loaded as written), every qubit as criterion, exact oracle.

Primary run uses the control-edge patch in control_fix.py (--variant control-fixed); the secondary
run uses the prototype unchanged (--variant unchanged).

Usage: python run.py --data-root DATA --eval-code EVAL_CODE --method-code METHOD_CODE --out OUT --variant V
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

METHODS = ["qpdg", "naive", "causal"]
LABEL = {"qpdg": "QPDG (Sec. III method)", "naive": "Naive classical PDG (def-use port)",
         "causal": "Causal classical PDG (data+control light cone)"}
INFLUENCE_EPS = 1e-9   # a qubit is influenced iff its reduced state moves by trace distance > this
BFIELDS = ["corpus", "circuit", "path", "n_qubits", "n_ops", "dynamic", "target", "method",
           "slice_size_fraction", "fidelity", "invalid"]
FFIELDS = ["corpus", "circuit", "path", "target", "method", "truth_size", "covered_true", "completeness",
           "complete"]


def _worker(job):
    corpus, name, rel, data_root, method_code, variant = job
    sys.path.insert(0, method_code)
    from qiskit import QuantumCircuit
    from common.corpus import load
    from common.evaluate import FIDELITY_EPS, materialise
    from common.oracle import OracleError, fidelity, reduced_states, trace_distance
    from qdg import QDG, EdgeType
    if variant == "control-fixed":
        from method_eval.control_fix import QDGControlFixed as QDG  # noqa: F811

    qc = load(Path(data_root) / rel)
    n, nops = qc.num_qubits, len(qc.data)
    dynamic = any(i.operation.name in ("measure", "reset", "if_else") for i in qc.data)
    try:
        base = reduced_states(qc, range(n))
    except OracleError as exc:
        return {"excluded": f"oracle: {exc}", "corpus": corpus, "circuit": name, "path": rel}
    full = QDG(qc, name)
    full.build(include_entanglement=True, include_control=True)
    causal = full.remove_edge_type(EdgeType.ENTANGLEMENT)
    brows, frows, cache = [], [], {}
    for t in range(n):
        slices = {"qpdg": full.entanglement_pruned_slice(t), "naive": full.naive_classical_backward_slice(t),
                  "causal": causal.backward_slice(t)}
        for m, s in slices.items():
            ids = frozenset(s)
            if ids not in cache:
                try:
                    cache[ids] = reduced_states(materialise(qc, ids), range(n))
                except OracleError as exc:
                    return {"excluded": f"oracle on slice: {exc}", "corpus": corpus, "circuit": name, "path": rel}
            f = fidelity(base[t], cache[ids][t])
            brows.append({"corpus": corpus, "circuit": name, "path": rel, "n_qubits": n, "n_ops": nops,
                          "dynamic": int(dynamic), "target": t, "method": m,
                          "slice_size_fraction": len(ids) / max(nops, 1), "fidelity": f,
                          "invalid": int(f < 1 - FIDELITY_EPS)})
        # Forward influence ground truth: perturb the target at the input (X), exact reduced states.
        pert = QuantumCircuit(*qc.qregs, *qc.cregs)
        pert.x(t)
        pert.compose(qc, inplace=True)
        try:
            moved = reduced_states(pert, range(n))
        except OracleError as exc:
            return {"excluded": f"oracle on perturbed circuit: {exc}", "corpus": corpus, "circuit": name, "path": rel}
        truth = {q for q in range(n) if trace_distance(base[q], moved[q]) > INFLUENCE_EPS}
        fwd = {"qpdg": full.forward_slice(t), "naive": full.naive_classical_forward_slice(t),
               "causal": causal.forward_slice(t)}
        for m, s in fwd.items():
            covered = {q for p in s if p in full.nodes for q in full.nodes[p].qubits} | {t}
            hit = len(truth & covered)
            frows.append({"corpus": corpus, "circuit": name, "path": rel, "target": t, "method": m,
                          "truth_size": len(truth), "covered_true": hit,
                          "completeness": hit / len(truth) if truth else 1.0,
                          "complete": int(truth <= covered)})
    return {"b": brows, "f": frows}


def summarise(brows, frows, out: Path):
    import numpy as np
    from common.evaluate import mcnemar_exact, rate, wilcoxon_paired
    corp = sorted({r["corpus"] for r in brows})
    tab, per = [], []
    for scope in ["ALL"] + corp:
        b = [r for r in brows if scope == "ALL" or r["corpus"] == scope]
        f = [r for r in frows if scope == "ALL" or r["corpus"] == scope]
        for m in METHODS:
            bm = [r for r in b if r["method"] == m]
            fm = [r for r in f if r["method"] == m]
            row = {"scope": scope, "n_circuits": len({r["path"] for r in bm}), "n_pairs": len(bm),
                   "method": LABEL[m], "invalid_slice_rate": rate([r["invalid"] for r in bm]),
                   "target_state_fidelity": float(np.mean([r["fidelity"] for r in bm])),
                   "slice_size_fraction_of_ops": float(np.mean([r["slice_size_fraction"] for r in bm])),
                   "forward_influence_completeness": float(np.mean([r["completeness"] for r in fm])),
                   "forward_complete_rate": rate([r["complete"] for r in fm])}
            (tab if scope == "ALL" else per).append(row)
    key = lambda r: (r["path"], r["target"])  # noqa: E731
    by = {m: {key(r): r for r in brows if r["method"] == m} for m in METHODS}
    fby = {m: {key(r): r for r in frows if r["method"] == m} for m in METHODS}
    keys = sorted(by["qpdg"])
    sound_both = [k for k in keys if not by["qpdg"][k]["invalid"] and not by["causal"][k]["invalid"]]
    tests = {
        "RQ1_qpdg_vs_naive_invalid": mcnemar_exact([by["qpdg"][k]["invalid"] for k in keys],
                                                   [by["naive"][k]["invalid"] for k in keys]),
        "RQ2_size_causal_minus_qpdg_sound_pairs": wilcoxon_paired(
            [by["causal"][k]["slice_size_fraction"] for k in sound_both],
            [by["qpdg"][k]["slice_size_fraction"] for k in sound_both]),
        "RQ2_qpdg_smaller_than_causal_pairs": sum(1 for k in sound_both if by["qpdg"][k]["slice_size_fraction"]
                                                  < by["causal"][k]["slice_size_fraction"]),
        "RQ3_qpdg_vs_naive_complete": mcnemar_exact([not fby["qpdg"][k]["complete"] for k in keys],
                                                    [not fby["naive"][k]["complete"] for k in keys]),
    }
    for name, rows in (("TAB1_method.csv", tab), ("TAB_per_corpus_method.csv", per)):
        with open(out / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    (out / "tests.json").write_text(json.dumps(tests, indent=2))
    return tab, tests


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--eval-code", required=True)
    ap.add_argument("--method-code", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--variant", choices=["control-fixed", "unchanged"], required=True,
                    help="control-fixed: primary (PROTOCOL 3.2); unchanged: secondary")
    ap.add_argument("--limit", type=int, default=None, help="debug only: first N circuits")
    a = ap.parse_args()
    from common.corpus import corpus_a
    root, out = Path(a.data_root), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    A = corpus_a(root, Path(a.eval_code))
    excluded = [{"corpus": e.corpus, "circuit": e.name, "path": e.path, "reason": f"load: {e.error}"}
                for e in A if e.qc is None]
    jobs = [(e.corpus, e.name, e.path, str(root), str(Path(a.method_code).resolve()), a.variant)
            for e in A if e.qc is not None][: a.limit]
    t0, brows, frows = time.time(), [], []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for i, res in enumerate(ex.map(_worker, jobs, chunksize=1), 1):
            if "excluded" in res:
                excluded.append({k: res[k] for k in ("corpus", "circuit", "path")} | {"reason": res["excluded"]})
            else:
                brows += res["b"]
                frows += res["f"]
            if i % 10 == 0:
                print(f"  {i}/{len(jobs)} circuits, {time.time() - t0:.0f}s", flush=True)
    for name, fields, rows in (("slice_records.csv", BFIELDS, brows), ("forward_records.csv", FFIELDS, frows)):
        with open(out / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    (out / "excluded.json").write_text(json.dumps(excluded, indent=2))
    tab, tests = summarise(brows, frows, out)
    for r in tab:
        print(f"  {r['method']:48s} invalid {r['invalid_slice_rate']:.3f}  fid {r['target_state_fidelity']:.6f}  "
              f"size {r['slice_size_fraction_of_ops']:.3f}  fwd {r['forward_influence_completeness']:.3f}")
    print(f"excluded circuits: {len(excluded)}; wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
