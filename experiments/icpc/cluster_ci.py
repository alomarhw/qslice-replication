"""Cluster-aware intervals and per-corpus breakdowns of the headline numbers (Deviation I-19, exploratory; item 5).

The pre-registered intervals treat pairs and units as independent, but they are qubits of the same circuits, and
several circuits implement one algorithm. For each headline quantity this computes the point estimate and three
95% percentile bootstrap intervals (10,000 resamples, seed 42): resampling pairs or units (as pre-registered),
resampling circuits, and resampling algorithm families (circuit names without size and variant suffixes), each
cluster carrying all its pairs or units. Per-corpus point estimates are reported alongside. Reads only committed
result files; computes nothing new about circuits.
Outputs (results/icpc/cluster_ci/): summary.json, by_corpus.csv.
Usage (from experiments/): python icpc/cluster_ci.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from common.evaluate import BOOT_RESAMPLES, SEED  # noqa: E402

RES = HERE / "results" / "icpc"
OUT = RES / "cluster_ci"
RQ1_SLICERS = ("du", "cpdg", "lc", "yz", "q", "lcq")
RQ3_SLICERS = ("du", "cpdg", "lc", "yz", "q")


def family(name: str) -> str:
    return re.sub(r"(_n\d+|_\d+|\d+)$", "", re.sub(r"_(indep|nativegates|mapped).*", "", name))


def boot(values, clusters, stat=np.mean):
    """95% percentile interval of stat over resampled clusters (each cluster keeps all its values)."""
    groups = defaultdict(list)
    for v, c in zip(values, clusters):
        groups[c].append(v)
    keys = list(groups)
    arrs = [np.asarray(groups[k], float) for k in keys]
    rng = np.random.default_rng(SEED)
    out = []
    for _ in range(BOOT_RESAMPLES):
        pick = rng.integers(0, len(keys), len(keys))
        out.append(stat(np.concatenate([arrs[i] for i in pick])))
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def summarize(values, rows, corpus_key="corpus"):
    v = np.asarray(values, float)
    return {"n": len(v), "n_circuits": len({r["path"] for r in rows}),
            "n_families": len({(r[corpus_key], family(r["circuit"])) for r in rows}), "point": float(v.mean()),
            "ci_units": boot(v, range(len(v))), "ci_circuits": boot(v, [r["path"] for r in rows]),
            "ci_families": boot(v, [(r[corpus_key], family(r["circuit"])) for r in rows])}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    res, by_corpus = {}, []

    def add(name, values, rows):
        res[name] = summarize(values, rows)
        groups = defaultdict(list)
        for v, r in zip(values, rows):
            groups[r["corpus"]].append(v)
        for c, vs in sorted(groups.items()):
            by_corpus.append({"quantity": name, "corpus": c, "n": len(vs), "point": float(np.mean(vs))})
        print(f"{name:28s} {res[name]['point']:.3f}  units {res[name]['ci_units'][0]:.3f}-{res[name]['ci_units'][1]:.3f}"
              f"  circuits {res[name]['ci_circuits'][0]:.3f}-{res[name]['ci_circuits'][1]:.3f}"
              f"  families {res[name]['ci_families'][0]:.3f}-{res[name]['ci_families'][1]:.3f}")

    # RQ1: corpus A pairs at |0...0>
    rq1 = defaultdict(dict)
    for path in (RES / "rq1" / "records.csv", RES / "cpdg" / "rq1_records.csv"):
        for r in csv.DictReader(open(path)):
            if r.get("applicable", "1") == "1":
                rq1[(r["path"], r["target"])][r["slicer"]] = r
    for s in RQ1_SLICERS:
        rows = [v[s] for v in rq1.values() if s in v]
        add(f"rq1_unsound_{s}", [r["sound"] != "1" for r in rows], rows)
        add(f"rq1_size_{s}", [float(r["size_fraction"]) for r in rows], rows)
        add(f"rq1_recall_{s}", [float(r["dep_recall"]) for r in rows], rows)
        add(f"rq1_precision_{s}", [float(r["dep_precision"]) for r in rows], rows)
    both = [v for v in rq1.values() if {"q", "lc"} <= v.keys() and v["q"]["sound"] == "1" and v["lc"]["sound"] == "1"]
    add("h2_size_lc_minus_q", [float(v["lc"]["size_fraction"]) - float(v["q"]["size_fraction"]) for v in both],
        [v["lc"] for v in both])

    # H3: robustness of S-q under R-haar
    rob = [r for r in csv.DictReader(open(RES / "rq2_robustness" / "pairs.csv")) if r["slicer"] == "q" and r["regime"] == "R-haar"]
    add("h3_robust_q", [r["robust"] == "1" for r in rob], rob)

    # RQ3: containment on the primary units, and H4's difference
    rec = defaultdict(dict)
    for path in (RES / "rq3" / "records.csv",):
        for r in csv.DictReader(open(path)):
            if r["analysis"] == "primary":
                rec[(r["path"], r["mutant"], r["target"])][r["slicer"]] = r
    meta = {k: next(iter(v.values())) for k, v in rec.items()}
    for r in csv.DictReader(open(RES / "cpdg" / "rq3_records.csv")):
        key = (r["path"], f"{r['path']}#{r['mutant']}", r["target"])
        if r["analysis"] == "primary" and key in rec:
            rec[key]["cpdg"] = meta[key] | {"contained": r["contained"], "size_fraction": r["size_fraction"], "slicer": "cpdg"}
    for s in RQ3_SLICERS:
        rows = [v[s] for v in rec.values() if s in v]
        add(f"rq3_contained_{s}", [r["contained"] == "1" for r in rows], rows)
    units = [v for v in rec.values() if {"q", "lc"} <= v.keys()]
    add("h4_contained_q_minus_lc", [float(v["q"]["contained"]) - float(v["lc"]["contained"]) for v in units],
        [v["lc"] for v in units])

    (OUT / "summary.json").write_text(json.dumps(res, indent=1))
    with open(OUT / "by_corpus.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["quantity", "corpus", "n", "point"])
        w.writeheader()
        w.writerows(by_corpus)
    return 0


if __name__ == "__main__":
    sys.exit(main())
