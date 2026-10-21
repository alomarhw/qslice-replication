"""Recompute the `category` column of results/icpc/rq1/misses.csv with the current classify_miss.

classify_miss had a bug (fixed 2026-10-21, JOURNAL.md): a register condition of a QASM 2 `if` was not
expanded to its bits, so feedback paths were missed and such misses were labelled "unreachable". Only
the category depends on classify_miss; every other RQ1 column is unchanged. The old category is kept
as `category_before_fix`.
Usage (from experiments/): python icpc/rq1_reclassify.py --data-root ../data --rq1 results/icpc/rq1
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--rq1", required=True)
    a = ap.parse_args()
    from common.corpus import load
    from icpc.rq1_run import classify_miss

    path = Path(a.rq1) / "misses.csv"
    rows = list(csv.DictReader(open(path)))
    if rows and "category_before_fix" in rows[0]:
        print("already reclassified")
        return 1
    circuits = {}
    for r in rows:
        if r["path"] not in circuits:
            circuits[r["path"]] = load(Path(a.data_root) / r["path"])
        r["category_before_fix"] = r["category"]
        r["category"] = classify_miss(circuits[r["path"]], int(r["position"]), int(r["target"]))
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(Counter((r["category_before_fix"], r["category"]) for r in rows if r["category_before_fix"] != r["category"]))
    print("unchanged:", sum(r["category_before_fix"] == r["category"] for r in rows), "of", len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
