"""MBFL baseline for RQ3 (PROTOCOL_ICPC.md section 4.3; Deviation I-2): mutation-based fault
localization as in Ishimoto et al. (EASE 2025), on the T2 sample (276 units) and every primary
Bugs4Q unit. Fixed before the run:

Program and reference. P is the program the developer has (the RQ3 mutant, or the buggy Bugs4Q
circuit); R is the correct one (the corpus circuit, or the fixed Bugs4Q circuit). The unit's
criterion qubit t is the observable-wrong qubit.
Tests. 21 inputs: |0...0> and 20 Haar product inputs (seed per circuit). Test tau FAILS when the
exact Z marginal of qubit t under P differs from that under R by more than 1e-6 (oracle Z).
MBFL mutants of P (QMutPy-style, one set per instruction k; barriers and delays skipped):
  delete k; for a 1-qubit gate, replace it by the first of x, h, z, s, t, y, sx that differs from it;
  for a 2-qubit gate, replace cx by cz and any other by cx; for a gate with a numeric first
  parameter, add pi/2 to it. Measurements, resets and if_else get the deletion mutant only.
A mutant KILLS test tau when qubit t's Z marginal under the mutant differs from that under P (1e-6).
Suspiciousness. Ochiai(m) = e_f / sqrt(F * (e_f + e_p)) (0 when undefined), with F the failing tests,
e_f / e_p the failing / passing tests that m kills; an instruction's score is the maximum over its
mutants.
EXAM (Ishimoto et al.): instructions ranked by descending score; with s* the best score of a
fault-site instruction, best = (#{s > s*} + 1) / n, worst = #{s >= s*} / n, average = (#{s > s*} +
(#{s = s*} + 1) / 2) / n. Reported over all instructions (n = instructions of P) and slice-filtered
over S-q and over S-lc (n = slice size; only when the slice contains the fault).
Output: results/icpc/mbfl/units.csv.
Usage (from experiments/): python icpc/mbfl.py --data-root ../data [--workers 12]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
OUT = HERE / "results" / "icpc" / "mbfl"
N_HAAR, EPS = 20, 1e-6
ONE_Q = ["x", "h", "z", "s", "t", "y", "sx"]
NON_GATES = {"measure", "reset", "if_else"}


def mbfl_mutants(qc):
    """(position, label, circuit) for every MBFL mutant of qc."""
    from icpc.mutate import _gate, _rebuild
    out = []
    for k, inst in enumerate(qc.data):
        op = inst.operation
        if op.name in ("barrier", "delay"):
            continue
        out.append((k, "delete", _rebuild(qc, {k: []})))
        if op.name in NON_GATES:
            continue
        if op.num_qubits == 1:
            g = next(x for x in ONE_Q if x != op.name)
            out.append((k, f"replace:{g}", _rebuild(qc, {k: [(_gate(g), inst.qubits, [])]})))
        elif op.num_qubits == 2:
            g = "cz" if op.name == "cx" else "cx"
            out.append((k, f"replace:{g}", _rebuild(qc, {k: [(_gate(g), inst.qubits, [])]})))
        if op.params and isinstance(op.params[0], (int, float)):
            m = op.to_mutable()
            m.params = [float(op.params[0]) + np.pi / 2] + list(op.params[1:])
            out.append((k, "param", _rebuild(qc, {k: [(m, inst.qubits, inst.clbits)]})))
    return out


def _z(qc, preps, n):
    from icpc import oracle_icpc as oi
    out = np.zeros((len(preps), n))
    for i, prep in enumerate(preps):
        rs = oi.reduced_states(oi.with_input(qc, prep), range(n))
        out[i] = [rs[q][0, 0].real for q in range(n)]
    return out


def exam(scores: dict, fault: set, universe):
    U = [k for k in universe]
    fs = [scores.get(k, 0.0) for k in U if k in fault]
    if not fs:
        return None, None, None
    s_star = max(fs)
    vals = [scores.get(k, 0.0) for k in U]
    gt, eq = sum(v > s_star for v in vals), sum(v == s_star for v in vals)
    n = len(U)
    return (gt + 1) / n, (gt + eq) / n, (gt + (eq + 1) / 2) / n


def _worker(job):
    key, units, data_root = job  # units: list of dicts with target, fault, slices, meta
    from icpc import oracle_icpc as oi
    t0 = time.time()
    P, R = _build(job[0], data_root)
    n = P.num_qubits
    rng = np.random.default_rng(int(hashlib.sha256(f"20261026:mbfl:{key}".encode()).hexdigest()[:12], 16))
    preps = [None] + [oi.haar_product_input(n, rng) for _ in range(N_HAAR)]
    try:
        zP, zR = _z(P, preps, n), _z(R, preps, n)
        muts = mbfl_mutants(P)
        zM = [(k, lab, _z(m, preps, n)) for k, lab, m in muts]
    except oi.OracleError as exc:
        return {"rows": [u["meta"] | {"excluded": f"oracle: {str(exc)[:120]}"} for u in units], "seconds": time.time() - t0}
    rows = []
    for u in units:
        t = u["target"]
        fail = np.abs(zP[:, t] - zR[:, t]) > EPS
        F = int(fail.sum())
        scores = defaultdict(float)
        for k, _, z in zM:
            kill = np.abs(z[:, t] - zP[:, t]) > EPS
            ef, ep = int((kill & fail).sum()), int((kill & ~fail).sum())
            och = ef / np.sqrt(F * (ef + ep)) if F and (ef + ep) else 0.0
            scores[k] = max(scores[k], och)
        fault = set(u["fault"])
        row = u["meta"] | {"n_ops": len(P.data), "n_mutants": len(muts), "failing_tests": F}
        for name, univ in (("all", range(len(P.data))), ("q", sorted(u["slices"]["q"])), ("lc", sorted(u["slices"]["lc"]))):
            b, w, a = exam(scores, fault, univ)
            row |= {f"exam_{name}_best": b, f"exam_{name}_worst": w, f"exam_{name}_avg": a,
                    f"fault_in_{name}": int(bool(fault & set(univ)))}
        rows.append(row)
    return {"rows": rows, "seconds": time.time() - t0}


def _build(key, data_root):
    """key: ('mutant', rel, mi) or ('bugs4q', stem)."""
    if key[0] == "mutant":
        from common.corpus import load
        from icpc.mutate import mutants
        _, rel, mi = key
        R = load(Path(data_root) / rel)
        return mutants(R, rel)[mi].circuit, R
    from icpc.rq3_bugs4q import _load
    return _load(key[1], "buggy"), _load(key[1], "fixed")


def jobs(data_root: str):
    groups = defaultdict(list)
    for it in map(json.loads, open(HERE / "results" / "llm" / "t2_items.jsonl")):
        if it["split"] != "score":
            continue
        rel, mi = it["key"].rsplit("#", 1)
        groups[("mutant", rel, int(mi))].append({"target": it["target"], "fault": it["fault_site"], "slices": it["slices"],
                                                "meta": {"source": "mutant", "unit": it["id"], "operator": it["operator"],
                                                         "corpus": it["corpus"], "target": it["target"]}})
    from slicers.registry import Slicers
    from icpc.rq3_bugs4q import _load
    for u in csv.DictReader(open(HERE / "results" / "icpc" / "rq3_bugs4q" / "units.csv")):
        if u["analysis"] != "primary":
            continue
        stem = u["bug_id"].replace("/", "__")
        t = int(u["target"])
        s = Slicers(_load(stem, "buggy"), stem)
        groups[("bugs4q", stem)].append({"target": t, "fault": [int(x) for x in u["fault_site"].split(";") if x],
                                         "slices": {"q": sorted(s.q(t)), "lc": sorted(s.lc(t))},
                                         "meta": {"source": "bugs4q", "unit": f"{u['bug_id']}:q{t}", "operator": "bugs4q",
                                                  "corpus": "Bugs4Q", "target": t}})
    return [(k, v, data_root) for k, v in groups.items()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--limit", type=int, default=None, help="debug only: first N circuits")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    J = jobs(str(Path(a.data_root).resolve()))[: a.limit]
    rows, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(_worker, j) for j in J]
        for i, f in enumerate(as_completed(futs), 1):
            rows += f.result()["rows"]
            if i % 20 == 0 or i == len(J):
                print(f"  {i}/{len(J)} circuits, {time.time() - t0:.0f}s", flush=True)
    rows.sort(key=lambda r: (r["source"], r["unit"]))
    with open(OUT / "units.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)
    print(f"units {len(rows)} from {len(J)} circuits; wrote {OUT / 'units.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
