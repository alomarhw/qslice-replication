"""Sizes of the programs and circuits each corpus contributes, for the data column of the related-work table.
Files are read, never executed. Code lines are non-blank, non-comment lines (scale_run.code_lines).
Usage (workspace root): python experiments/icpc/corpus_sizes.py --data-root <data-root>  -> results/icpc/corpus_sizes.json
"""
import argparse
import csv
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
from icpc.scale_run import code_lines  # noqa: E402

RES = ROOT / "experiments" / "results" / "icpc"


def rows(p):
    return list(csv.DictReader(open(p)))


def lines_summary(ns):
    ns = sorted(ns)
    return {"files": len(ns), "median_lines": st.median(ns), "max_lines": ns[-1], "total_lines": sum(ns)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    root = Path(ap.parse_args().data_root)
    out = {}
    circ = {}
    for r in rows(RES / "rq1" / "pairs.csv"):
        circ[r["path"]] = (r["corpus"], int(r["n_qubits"]), int(r["n_ops"]))
    by = defaultdict(list)
    for c, q, o in circ.values():
        by[c].append((q, o))
    allq = [q for _, q, _ in circ.values()]
    allo = [o for _, _, o in circ.values()]
    out["corpus_a"] = {"circuits": len(circ), "by_corpus": {c: len(v) for c, v in by.items()},
                       "min_qubits": min(allq), "max_qubits": max(allq), "min_ops": min(allo),
                       "median_ops": st.median(allo), "max_ops": max(allo)}
    for name, csv_path in (("bugs4q", RES / "tool_acceptance" / "tool-v7" / "t3_bugs4q.csv"),
                           ("textbook", RES / "tool_coverage" / "textbook_v7.csv")):
        files = [r["file"].replace("<data-root>", str(root)) for r in rows(csv_path) if r["uses_qiskit"] == "1"]
        out[name] = lines_summary(code_lines(Path(f)) for f in files)
    out["lintq"] = lines_summary(code_lines(f) for f in sorted((root / "lintq" / "exp_v08" / "files_selected").glob("*.py")))
    qh = [r for r in rows(RES / "qhe" / "tasks.csv") if r["set"] == "hard"]
    out["qhe"] = lines_summary(int(r["code_lines"]) for r in qh)
    (RES / "corpus_sizes.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
