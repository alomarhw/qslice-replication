"""S-cpdg (Deviation I-12) scored exactly as the pre-registered runs score the other slicers.

  rq1       corpus A pairs at |0...0>: soundness (oracle), dependence recall/precision against the §2.1 ground
            truth, and every missed dependence classified by icpc/rq1_run.py::classify_miss.
  rq3       the RQ3 primary and secondary units (results/icpc/rq3/units.csv): containment of the fault site
            and slice size on the mutant circuit, as icpc/rq3_run.py defines them.
  families  the structure families: soundness and dependence recall, as icpc/families_run.py.
Outputs (results/icpc/cpdg/): rq1_records.csv, rq1_misses.csv, rq3_records.csv, families_rows.csv.
Usage (from experiments/): python icpc/cpdg_run.py --data-root ../data --eval-code ../selection [--part all] [--workers 8]
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
OUT = HERE / "results" / "icpc" / "cpdg"


def _score(qc, t, sl, base, inf):
    from common.evaluate import materialise
    from icpc import oracle_icpc as oi
    f = oi.uhlmann_fidelity(base[t], oi.reduced_states(materialise(qc, sl), range(qc.num_qubits))[t])
    hit = len(sl & inf)
    return {"size": len(sl), "size_fraction": len(sl) / max(len(qc.data), 1), "fidelity": f,
            "sound": int(f >= 1 - oi.FIDELITY_EPS), "n_influencing": len(inf),
            "dep_recall": hit / len(inf) if inf else 1.0, "dep_precision": hit / len(sl) if sl else 1.0,
            "n_missed": len(inf - sl)}


def _rq1(job):
    corpus, name, rel, data_root = job
    from common.corpus import load
    from icpc import oracle_icpc as oi
    from icpc.cpdg import cpdg_slice
    from icpc.influence import influence, influence_sets
    from icpc.rq1_run import classify_miss
    qc = load(Path(data_root) / rel)
    n = qc.num_qubits
    try:
        base = oi.reduced_states(qc, range(n))
        inf = influence_sets(influence(qc), n)
    except oi.OracleError as exc:
        return {"excluded": str(exc)[:200], "path": rel}
    dyn = int(any(i.operation.name in ("measure", "reset", "if_else") for i in qc.data))
    recs, miss = [], []
    for t in range(n):
        sl = cpdg_slice(qc, t)
        recs.append({"corpus": corpus, "circuit": name, "path": rel, "n_qubits": n, "n_ops": len(qc.data),
                     "dynamic": dyn, "target": t, "slicer": "cpdg"} | _score(qc, t, sl, base, inf[t]))
        for k in sorted(inf[t] - sl):
            miss.append({"corpus": corpus, "circuit": name, "path": rel, "target": t, "slicer": "cpdg", "position": k,
                         "gate": qc.data[k].operation.name, "category": classify_miss(qc, k, t)})
    return {"recs": recs, "miss": miss}


def _rq3(job):
    rel, mi, units, data_root = job
    from common.corpus import load
    from icpc.cpdg import cpdg_slice
    from icpc.mutate import mutants
    R = load(Path(data_root) / rel)
    P = mutants(R, rel)[mi].circuit
    out = []
    for u in units:
        fault = {int(x) for x in u["fault_site"].split(";") if x}
        sl = cpdg_slice(P, int(u["target"]))
        out.append({"path": rel, "mutant": mi, "target": u["target"], "analysis": u["analysis"], "slicer": "cpdg",
                    "contained": int(bool(sl & fault)), "size": len(sl), "size_fraction": len(sl) / max(len(P.data), 1)})
    return out


def _family(job):
    family, name = job
    from families.generate import families
    from icpc import oracle_icpc as oi
    from icpc.cpdg import cpdg_slice
    from icpc.influence import influence, influence_sets
    qc = next(c for f, n, c in families() if f == family and n == name)
    n = qc.num_qubits
    try:
        base = oi.reduced_states(qc, range(n))
        inf = influence_sets(influence(qc), n)
    except oi.OracleError:
        return []
    return [{"family": family, "circuit": name, "n_qubits": n, "n_ops": len(qc.data), "target": t, "slicer": "cpdg"}
            | _score(qc, t, cpdg_slice(qc, t), base, inf[t]) for t in range(n)]


def _write(name, rows):
    with open(OUT / name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--eval-code", default="../selection")
    ap.add_argument("--part", default="all", choices=["all", "rq1", "rq3", "families"])
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    root = str(Path(a.data_root).resolve())
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        if a.part in ("all", "rq1"):
            from common.corpus import corpus_a
            A = [e for e in corpus_a(Path(root), Path(a.eval_code)) if e.qc is not None]
            recs, miss = [], []
            for f in as_completed([ex.submit(_rq1, (e.corpus, e.name, e.path, root)) for e in A]):
                r = f.result()
                recs += r.get("recs", [])
                miss += r.get("miss", [])
            _write("rq1_records.csv", sorted(recs, key=lambda r: (r["path"], r["target"])))
            _write("rq1_misses.csv", miss)
            print(f"rq1: {len(recs)} pairs, unsound {sum(not r['sound'] for r in recs)}, {time.time() - t0:.0f}s", flush=True)
        if a.part in ("all", "rq3"):
            groups = defaultdict(list)
            for u in csv.DictReader(open(HERE / "results" / "icpc" / "rq3" / "units.csv")):
                groups[(u["path"], int(u["mutant"].rsplit("#", 1)[1]))].append(u)
            rows = []
            for f in as_completed([ex.submit(_rq3, (p, m, us, root)) for (p, m), us in groups.items()]):
                rows += f.result()
            _write("rq3_records.csv", rows)
            pri = [r for r in rows if r["analysis"] == "primary"]
            print(f"rq3: {len(rows)} units, primary containment {sum(r['contained'] for r in pri) / len(pri):.4f}, {time.time() - t0:.0f}s", flush=True)
        if a.part in ("all", "families"):
            from families.generate import families
            rows = []
            for f in as_completed([ex.submit(_family, (fam, n)) for fam, n, _ in families()]):
                rows += f.result()
            _write("families_rows.csv", rows)
            print(f"families: {len(rows)} rows, unsound {sum(not r['sound'] for r in rows)}, {time.time() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
