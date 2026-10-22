"""RQ3 on real bugs (PROTOCOL_ICPC.md section 4.1-4.3): the 11 circuit-semantic Bugs4Q bugs that the
pre-registered triage (bugs4q/TRIAGE.md, triage.csv) includes.

The fixed circuit plays the role of the original and the buggy circuit that of the mutant: the
outcome (killed / injured / alive) and the units come from the exact Z and rho oracles at |0...0>,
every slicer slices the BUGGY circuit, and the fault site is the triage's aligned instruction diff
(positions in the buggy circuit). Metrics as in icpc/rq3_run.py: containment, size, EXAM (in-slice
and global), the random equal-size baseline, C-Q4 and its S-qW remedy.
Outputs (results/icpc/rq3_bugs4q/): bugs.csv, units.csv, records.csv.
Usage (from experiments/): python icpc/rq3_bugs4q.py
"""

from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from icpc.rq3_run import N_RANDOM, SLICERS, _is_unitary, exam_scores  # noqa: E402

OUT = HERE / "results" / "icpc" / "rq3_bugs4q"
CIRC = HERE / "bugs4q" / "circuits"


def _load(stem: str, which: str):
    from common.corpus import load, prepare
    q = CIRC / f"{stem}.{which}.qasm"
    if q.exists():
        return load(q)
    from qiskit import qpy
    with open(CIRC / f"{stem}.{which}.qpy", "rb") as fh:
        return prepare(qpy.load(fh)[0])


def main() -> int:
    from icpc import oracle_icpc as oi
    from slicers.registry import Slicers, qslice_set
    OUT.mkdir(parents=True, exist_ok=True)
    tri = [r for r in csv.DictReader(open(HERE / "bugs4q" / "triage.csv")) if r["included"] == "1"]
    brows, urows, rrows = [], [], []
    for r in tri:
        stem = r["bug_id"].replace("/", "__")
        buggy, fixed = _load(stem, "buggy"), _load(stem, "fixed")
        n = buggy.num_qubits
        fault = {int(x) for x in r["fault_site_positions"].split(";") if x != ""}
        row = {"bug_id": r["bug_id"], "stage": r["stage"], "kind": r["kind"], "n_qubits": n,
               "n_ops_buggy": len(buggy.data), "n_ops_fixed": len(fixed.data), "fault_site": r["fault_site_positions"]}
        if fixed.num_qubits != n:
            brows.append(row | {"outcome": "excluded", "note": "buggy and fixed differ in qubit count"})
            continue
        try:
            base, mb = oi.reduced_states(fixed, range(n)), oi.reduced_states(buggy, range(n))
        except oi.OracleError as exc:  # section 10: an oracle exclusion, listed with its reason
            brows.append(row | {"outcome": "excluded", "note": f"oracle: {str(exc)[:160]}"})
            continue
        z_wrong = [q for q in range(n) if abs(base[q][0, 0].real - mb[q][0, 0].real) > 1e-6]
        r_wrong = [q for q in range(n) if oi.uhlmann_fidelity(base[q], mb[q]) < 1 - oi.FIDELITY_EPS]
        outcome = "killed" if z_wrong else "injured" if r_wrong else "alive"
        brows.append(row | {"outcome": outcome, "z_wrong": ";".join(map(str, z_wrong)), "rho_wrong": ";".join(map(str, r_wrong))})
        if outcome == "alive":
            continue
        units = [(t, "primary") for t in z_wrong] if outcome == "killed" else [(t, "secondary") for t in r_wrong]
        wrong = z_wrong if outcome == "killed" else r_wrong
        s = Slicers(buggy, stem)
        nops = len(buggy.data)
        rrng = np.random.default_rng(int(hashlib.sha256(f"20261024:random:bugs4q:{r['bug_id']}".encode()).hexdigest()[:12], 16))
        for t, analysis in units:
            slices = {k: s.get(k)(t) for k in SLICERS}
            slices["full"] = set(range(nops))
            urow = {"bug_id": r["bug_id"], "stage": r["stage"], "analysis": analysis, "target": t, "n_ops": nops,
                    "n_qubits": n, "dynamic": int(not _is_unitary(buggy))}
            for k, sl in slices.items():
                ex_s, ex_g = exam_scores(sl, fault, nops)
                rrows.append(urow | {"slicer": k, "contained": int(bool(sl & fault)), "size": len(sl),
                                     "size_fraction": len(sl) / nops, "exam_slice": ex_s, "exam_global": ex_g})
            k_size = len(slices["q"])
            cont, exs = [], []
            for _ in range(N_RANDOM):
                pick = set(rrng.choice(nops, size=k_size, replace=False).tolist()) if k_size else set()
                cont.append(bool(pick & fault))
                exs.append(exam_scores(pick, fault, nops)[1])
            rrows.append(urow | {"slicer": "random", "contained": float(np.mean(cont)), "size": k_size,
                                 "size_fraction": k_size / nops, "exam_slice": None, "exam_global": float(np.mean(exs))})
            cq4 = int(bool(slices["lc"] & fault) and not bool(slices["q"] & fault))
            remedy = int(bool(qslice_set(buggy, wrong, slicers=s) & fault)) if cq4 else ""
            urows.append(urow | {"fault_site": r["fault_site_positions"], "cq4": cq4, "cq4_remedy_contains": remedy,
                                 "wrong_qubits": ";".join(map(str, wrong))})
    for name, rows in (("bugs.csv", brows), ("units.csv", urows), ("records.csv", rrows)):
        with open(OUT / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for x in rows for k in x)))
            w.writeheader()
            w.writerows(rows)
    print(f"bugs {len(brows)}: {dict((o, sum(b['outcome'] == o for b in brows)) for o in ('killed', 'injured', 'alive', 'excluded'))}; "
          f"units {len(urows)}; wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
