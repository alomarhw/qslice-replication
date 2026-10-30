"""Deviation I-28, forward pass: qdg_forward against forward reachability in the graph of `lc`, every operation of corpus A.
Usage (from experiments/): python icpc/one_pass_forward_check.py --data-root DATA -> results/icpc/one_pass/forward.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import networkx as nx

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "qslice"))
from one_pass import qdg_forward  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    a = ap.parse_args()
    from common.corpus import load
    from slicers.registry import Slicers
    paths = sorted({r["path"] for r in csv.DictReader(open(HERE / "results" / "icpc" / "rq1" / "pairs.csv"))})
    ops, equal, diffs = 0, 0, []
    for path in paths:
        qc = load(Path(a.data_root) / path)
        g = Slicers(qc, path).causal.graph
        for k in range(len(qc.data)):
            ops += 1
            ref = nx.descendants(g, k) | {k}
            mine = qdg_forward(qc, k)
            equal += mine == ref
            if mine != ref:
                diffs.append({"path": path, "op": k, "extra": sorted(mine - ref), "missing": sorted(ref - mine)})
    out = {"ops": ops, "equal": equal, "diffs": diffs[:50]}
    (HERE / "results" / "icpc" / "one_pass" / "forward.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({"ops": ops, "equal": equal, "differ": len(diffs)}))


if __name__ == "__main__":
    main()
