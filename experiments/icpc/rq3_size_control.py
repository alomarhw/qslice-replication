"""Size-matched random control for every rule's RQ3 containment (Deviation I-19, exploratory; review item 6).

RQ3 compares S-q with a random set of S-q's size (icpc/rq3_run.py, 100 draws). Containment grows with size, so
here every rule is compared with a random set of its own size on each unit. The chance that k instructions drawn
uniformly from the n of the mutant contain one of its f fault-site instructions is exactly
1 - C(n - f, k) / C(n, k), so no sampling is needed. Per rule: containment, the mean of that chance, and their
difference with circuit- and family-cluster bootstrap intervals (icpc/cluster_ci.py). Reads committed files only.
Output: results/icpc/rq3_size_control/summary.json.
Usage (from experiments/): python icpc/rq3_size_control.py
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from icpc.cluster_ci import RES, family, summarize  # noqa: E402

OUT = RES / "rq3_size_control"


def chance(n: int, f: int, k: int) -> float:
    return 1.0 - comb(n - f, k) / comb(n, k) if k <= n else 1.0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    fault = {(u["path"], u["mutant"], u["target"]): len([x for x in u["fault_site"].split(";") if x])
             for u in csv.DictReader(open(RES / "rq3" / "units.csv")) if u["analysis"] == "primary"}
    rec = defaultdict(dict)
    for r in csv.DictReader(open(RES / "rq3" / "records.csv")):
        if r["analysis"] == "primary":
            rec[(r["path"], r["mutant"], r["target"])][r["slicer"]] = r
    meta = {k: next(iter(v.values())) for k, v in rec.items()}
    for r in csv.DictReader(open(RES / "cpdg" / "rq3_records.csv")):
        key = (r["path"], f"{r['path']}#{r['mutant']}", r["target"])
        if r["analysis"] == "primary" and key in rec:
            rec[key]["cpdg"] = meta[key] | {"slicer": "cpdg", "contained": r["contained"], "size": r["size"]}
    res = {}
    for s in ("du", "cpdg", "lc", "yz", "q"):
        rows = [v[s] for k, v in rec.items() if s in v and k in fault]
        keys = [k for k, v in rec.items() if s in v and k in fault]
        ch = [chance(int(r["n_ops"]), fault[k], int(r["size"])) for r, k in zip(rows, keys)]
        ct = [float(r["contained"] == "1") for r in rows]
        res[s] = {"contained": summarize(ct, rows), "random_same_size": summarize(ch, rows),
                  "difference": summarize([a - b for a, b in zip(ct, ch)], rows)}
        d = res[s]["difference"]
        print(f"{s:5s} contained {res[s]['contained']['point']:.3f}  random {res[s]['random_same_size']['point']:.3f}  "
              f"diff {d['point']:+.3f}  families {d['ci_families'][0]:+.3f}..{d['ci_families'][1]:+.3f}")
    (OUT / "summary.json").write_text(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
