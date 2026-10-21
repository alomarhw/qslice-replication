"""RQ3 fault localization on seeded faults (PROTOCOL_ICPC.md sections 4.1-4.3; Deviation I-2).

Per corpus-A circuit: generate mutants (icpc/mutate.py), drop equivalent ones, classify the rest at
|0...0> as killed (some qubit's Z marginal differs), injured (some rho_q differs, no Z marginal does)
or alive. Units: (killed mutant, Z-wrong qubit) [primary]; (injured mutant, rho-wrong qubit) [secondary].
Every slicer slices the MUTANT (buggy) circuit for the unit's qubit. Per (unit, slicer):
  contained   the slice contains a fault-site instruction
  size        instructions in the slice
  exam_slice  rank of the first fault-site instruction in the slice ordered latest first / size
  exam_global (slice latest first, then the rest latest first): rank of first fault instruction / all
Also: random equal-size baseline (100 draws), C-Q4 (fault in S-lc, not in S-q) and its S-qW remedy.

Outputs (results/icpc/rq3/): mutants.csv, units.csv, records.csv, excluded.json.
Usage: python icpc/rq3_run.py --data-root DATA --eval-code ../selection --out OUT [--workers 12]
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

SLICERS = ["du", "lc", "yz", "q"]
N_EQUIV_INPUTS, N_RANDOM = 20, 100
DYNAMIC = ("measure", "reset", "if_else")


def _is_unitary(qc) -> bool:
    return not any(i.operation.name in DYNAMIC for i in qc.data)


def equivalent(orig, mut, oi, rng) -> tuple[bool, str]:
    n = orig.num_qubits
    if n <= 10 and _is_unitary(orig) and _is_unitary(mut):
        from qiskit.quantum_info import Operator
        return bool(Operator(orig).equiv(Operator(mut))), "operator"
    for prep in [None] + [oi.haar_product_input(n, rng) for _ in range(N_EQUIV_INPUTS)]:
        a = oi.reduced_states(oi.with_input(orig, prep), range(n))
        b = oi.reduced_states(oi.with_input(mut, prep), range(n))
        if any(oi.uhlmann_fidelity(a[q], b[q]) < 1 - oi.FIDELITY_EPS for q in range(n)):
            return False, "states"
    return True, "states"


def exam_scores(slice_pos, fault, n_ops):
    order_in = sorted(slice_pos, reverse=True)
    rank = next((i + 1 for i, p in enumerate(order_in) if p in fault), None)
    exam_slice = rank / len(order_in) if rank else None
    order_all = order_in + sorted(set(range(n_ops)) - set(slice_pos), reverse=True)
    grank = next(i + 1 for i, p in enumerate(order_all) if p in fault)
    return exam_slice, grank / n_ops


def _worker(job):
    corpus, name, rel, data_root = job
    from common.corpus import load
    from icpc import oracle_icpc as oi
    from icpc.mutate import PROVENANCE, mutants
    from slicers.registry import Slicers, qslice_set

    t0 = time.time()
    qc = load(Path(data_root) / rel)
    n = qc.num_qubits
    rng = np.random.default_rng(int(hashlib.sha256(f"20261022:equiv:{rel}".encode()).hexdigest()[:12], 16))
    rrng = np.random.default_rng(int(hashlib.sha256(f"20261024:random:{rel}".encode()).hexdigest()[:12], 16))
    try:
        base = oi.reduced_states(qc, range(n))
    except oi.OracleError as exc:
        return {"excluded": f"oracle: {exc}", "corpus": corpus, "circuit": name, "path": rel}
    mrows, urows, rrows = [], [], []
    for mi, m in enumerate(mutants(qc, rel)):
        mid = f"{rel}#{mi}"
        row = {"corpus": corpus, "circuit": name, "path": rel, "mutant": mid, "operator": m.operator,
               "provenance": PROVENANCE[m.operator], "site": m.site, "fault_site": ";".join(map(str, sorted(m.fault_site))),
               "n_ops_mutant": len(m.circuit.data)}
        try:
            eq, rule = equivalent(qc, m.circuit, oi, rng)
            row |= {"equivalent": int(eq), "equivalence_rule": rule}
            if eq:
                row["outcome"] = "equivalent"
                mrows.append(row)
                continue
            mb = oi.reduced_states(m.circuit, range(n))
        except oi.OracleError as exc:
            row |= {"outcome": "excluded", "note": str(exc)[:200]}
            mrows.append(row)
            continue
        z_wrong = [q for q in range(n) if abs(base[q][0, 0].real - mb[q][0, 0].real) > 1e-6]
        r_wrong = [q for q in range(n) if oi.uhlmann_fidelity(base[q], mb[q]) < 1 - oi.FIDELITY_EPS]
        outcome = "killed" if z_wrong else "injured" if r_wrong else "alive"
        row |= {"outcome": outcome, "z_wrong": ";".join(map(str, z_wrong)), "rho_wrong": ";".join(map(str, r_wrong))}
        mrows.append(row)
        if outcome == "alive":
            continue
        units = [(t, "primary") for t in z_wrong] if outcome == "killed" else [(t, "secondary") for t in r_wrong]
        wrong = z_wrong if outcome == "killed" else r_wrong
        s = Slicers(m.circuit, name)
        nops = len(m.circuit.data)
        fault = set(m.fault_site)
        for t, analysis in units:
            slices = {k: s.get(k)(t) for k in SLICERS}
            slices["full"] = set(range(nops))
            urow = {"corpus": corpus, "circuit": name, "path": rel, "mutant": mid, "operator": m.operator,
                    "analysis": analysis, "target": t, "n_ops": nops, "n_qubits": n,
                    "dynamic": int(not _is_unitary(m.circuit))}
            for k, sl in slices.items():
                ex_s, ex_g = exam_scores(sl, fault, nops)
                rrows.append(urow | {"slicer": k, "contained": int(bool(sl & fault)), "size": len(sl),
                                     "size_fraction": len(sl) / nops, "exam_slice": ex_s, "exam_global": ex_g})
            # random equal-size baseline (size of the S-q slice)
            k_size = len(slices["q"])
            cont, exs = [], []
            for _ in range(N_RANDOM):
                pick = set(rrng.choice(nops, size=k_size, replace=False).tolist()) if k_size else set()
                cont.append(bool(pick & fault))
                exs.append(exam_scores(pick, fault, nops)[1])
            rrows.append(urow | {"slicer": "random", "contained": float(np.mean(cont)), "size": k_size,
                                 "size_fraction": k_size / nops, "exam_slice": None, "exam_global": float(np.mean(exs))})
            cq4 = int(bool(slices["lc"] & fault) and not bool(slices["q"] & fault))
            remedy = ""
            if cq4:
                remedy = int(bool(qslice_set(m.circuit, wrong, slicers=s) & fault))
            urows.append(urow | {"fault_site": row["fault_site"], "cq4": cq4, "cq4_remedy_contains": remedy,
                                 "wrong_qubits": ";".join(map(str, wrong))})
    return {"m": mrows, "u": urows, "r": rrows, "seconds": time.time() - t0}


def _write(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r)) if rows else []
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


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
    jobs = sorted([(e.corpus, e.name, e.path, str(root)) for e in A if e.qc is not None][: a.limit], key=lambda j: -sizes[j[2]])
    M, U, R, t0 = [], [], [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for i, res in enumerate(ex.map(_worker, jobs, chunksize=1), 1):
            if "excluded" in res:
                excluded.append({k: res[k] for k in ("corpus", "circuit", "path")} | {"reason": res["excluded"]})
            else:
                M += res["m"]; U += res["u"]; R += res["r"]
            if i % 10 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} circuits, {time.time() - t0:.0f}s", flush=True)
    _write(out / "mutants.csv", sorted(M, key=lambda r: r["mutant"]))
    _write(out / "units.csv", sorted(U, key=lambda r: (r["mutant"], r["target"])))
    _write(out / "records.csv", sorted(R, key=lambda r: (r["mutant"], r["target"], r["slicer"])))
    (out / "excluded.json").write_text(json.dumps(excluded, indent=2))
    print(f"mutants {len(M)}, units {len(U)}; wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
