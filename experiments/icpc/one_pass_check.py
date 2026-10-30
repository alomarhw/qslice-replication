"""Deviation I-28: the one-pass QDG slice against the graph slice `lc`, and its cost from the circuit.

Check: on the 784 RQ1 pairs, qdg_slice(bits="graph") and qdg_slice(bits="def4") against Slicers.lc.
Cost: on the RQ4 circuits (F-depth, width sweeps) and corpus L, the one-pass slice of every criterion from the circuit,
against building the graph without entanglement edges plus `lc` per criterion. Single process, sequential.
Usage (from experiments/): python icpc/one_pass_check.py --data-root ../data  -> results/icpc/one_pass/
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "qslice"))
from one_pass import qdg_slice  # noqa: E402

OUT = HERE / "results" / "icpc" / "one_pass"
RES = HERE / "results" / "icpc"


def rows(p):
    return list(csv.DictReader(open(p)))


def check(data_root):
    from common.corpus import load
    from slicers.registry import Slicers
    pairs = rows(RES / "rq1" / "pairs.csv")
    diffs, n, eq_graph, eq_def4 = [], 0, 0, 0
    for path in sorted({r["path"] for r in pairs}):
        qc = load(Path(data_root) / path)
        s = Slicers(qc, path)
        for t in sorted({int(r["target"]) for r in pairs if r["path"] == path}):
            lc, g, d = s.lc(t), qdg_slice(qc, t, "graph"), qdg_slice(qc, t, "def4")
            n += 1
            eq_graph += g == lc
            eq_def4 += d == lc
            if g != lc or d != lc:
                diffs.append({"path": path, "target": t, "lc": len(lc), "graph": len(g), "def4": len(d),
                              "graph_minus_lc": sorted(g - lc), "lc_minus_graph": sorted(lc - g),
                              "def4_minus_lc": sorted(d - lc), "lc_minus_def4": sorted(lc - d)})
    return {"pairs": n, "graph_equal": eq_graph, "def4_equal": eq_def4}, diffs


def cost(data_root):
    from common.corpus import load
    from families.generate import f_ghz, f_inv, families
    from method_eval.control_fix import QDGControlFixed
    circuits = []
    fam = {(f, nm): c for f, nm, c in families() if f == "F-depth"}
    for r in rows(RES / "cost" / "circuits.csv"):
        if r["kind"] == "F-depth":
            circuits.append((r["kind"], r["name"], fam[("F-depth", r["name"])]))
        elif r["kind"] == "width-F-ghz":
            n, k = (int(x[1:]) for x in r["name"].split("_"))
            circuits.append((r["kind"], r["name"], f_ghz(n, k)))
        elif r["kind"] == "width-F-inv":
            w, d = (int(x[1:]) for x in r["name"].split("_"))
            circuits.append((r["kind"], r["name"], f_inv(w, d)))
    for r in rows(RES / "corpus_l" / "circuits.csv"):
        circuits.append(("corpus-L", r["name"], load(Path(data_root) / r["path"])))
    out = []
    for kind, name, qc in circuits:
        n = qc.num_qubits
        per = []
        t0 = time.perf_counter()
        for t in range(n):
            t1 = time.perf_counter()
            qdg_slice(qc, t, "graph")
            per.append(time.perf_counter() - t1)
        one_all = time.perf_counter() - t0
        t0 = time.perf_counter()
        g = QDGControlFixed(qc, name)
        g.build(include_entanglement=False, include_control=True)
        build = time.perf_counter() - t0
        t0 = time.perf_counter()
        for t in range(n):
            g.backward_slice(t)
        trav = time.perf_counter() - t0
        out.append({"kind": kind, "name": name, "n_qubits": n, "n_ops": len(qc.data),
                    "one_pass_max_ms": round(1000 * max(per), 3), "one_pass_median_ms": round(1000 * st.median(per), 3),
                    "one_pass_all_s": round(one_all, 4), "graph_build_s": round(build, 4), "graph_slices_s": round(trav, 4)})
        print(kind, name, out[-1]["one_pass_max_ms"], "ms", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    summ, diffs = check(a.data_root)
    print(json.dumps(summ))
    (OUT / "diffs.json").write_text(json.dumps(diffs, indent=1) + "\n")
    c = cost(a.data_root)
    with open(OUT / "cost.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(c[0]))
        w.writeheader()
        w.writerows(c)
    summ["cost_circuits"] = len(c)
    summ["one_pass_max_ms_overall"] = max(r["one_pass_max_ms"] for r in c)
    summ["one_pass_all_max_s"] = max(r["one_pass_all_s"] for r in c)
    summ["graph_build_max_s"] = max(r["graph_build_s"] for r in c)
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps(summ))


if __name__ == "__main__":
    main()
