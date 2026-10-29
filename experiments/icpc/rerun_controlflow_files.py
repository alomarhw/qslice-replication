"""Rerun after Deviation I-26: the S1 and Qiskit HumanEval rows of the files that call Qiskit's in-circuit control flow.

The interpreter change of I-26 touches only `with` blocks over if_test, while_loop, for_loop and switch, so only files
that call them can trace differently. Their rows are recomputed with scale_run.s1_one (unchanged) and written, with
every other row copied unchanged, to results/icpc/<run>__rerun-20261028/; the old results stay where they are. The
summary statistics the paper uses are compared, old against new.
Usage (workspace root): python experiments/icpc/rerun_controlflow_files.py --data-root <data-root>
"""
import argparse
import csv
import json
import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
from icpc.scale_run import S1_LIMIT, s1_one  # noqa: E402
from tool.corpus.hardlimit import run_all  # noqa: E402

RES = ROOT / "experiments" / "results" / "icpc"
CALLS = re.compile(r"\.(if_test|while_loop|for_loop|switch)\(")
TAG = "__rerun-20261028"


def stats(rows, code_col="code_lines"):
    ok = [r for r in rows if not r.get("error")]
    times = sorted(sum(float(r[k]) for k in ("t_srcml", "t_interp", "t_slice", "t_srcslice", "t_profile")) for r in ok)
    share = [int(x) / int(r[code_col]) for r in ok for x in str(r["slice_lines"]).split(";") if x and int(r[code_col])]
    return {"rows": len(rows), "sliced": len(ok), "median_ms": round(1000 * st.median(times), 1) if times else None,
            "median_slice_share": round(st.median(share), 4) if share else None,
            "may_files": sum(int(r.get("may_ops") or 0) > 0 for r in ok)}


def redo(rows, path_of, key):
    hit = [r for r in rows if CALLS.search(path_of(r).read_text(errors="replace"))]
    jobs = [(path_of(r), r[key]) for r in hit]
    new = {r["file"]: r for r in run_all(s1_one, jobs, S1_LIMIT, lambda p, rel: {"file": rel, "error": "timeout"}, 2)}
    out = []
    for r in rows:
        if r in hit:
            n = new[r[key]]
            out.append({**{k: "" for k in r}, **{k: v for k, v in r.items() if k not in n and k not in
                        ("ops", "qubits", "may_ops", "error", "slice_lines", "sliced_qubits")}, **n})
        else:
            out.append(r)
    return out, [r[key] for r in hit]


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    a = ap.parse_args()
    corpus = Path(a.data_root) / "lintq" / "exp_v08" / "files_selected"
    report = {}
    s1 = list(csv.DictReader(open(RES / "scale" / "s1_lintq.csv")))
    s1n, s1_files = redo(s1, lambda r: corpus / r["file"], "file")
    write(RES / f"scale{TAG}" / "s1_lintq.csv", s1n)
    report["s1"] = {"rerun_files": s1_files, "old": stats(s1), "new": stats(s1n)}
    qh = list(csv.DictReader(open(RES / "qhe" / "tasks.csv")))
    progs = RES / "qhe" / "programs"
    qhn, qh_files = redo(qh, lambda r: progs / r["file"], "file")
    write(RES / f"qhe{TAG}" / "tasks.csv", qhn)
    for name in ("standard", "hard"):
        report[f"qhe_{name}"] = {"old": stats([r for r in qh if r["set"] == name]),
                                 "new": stats([r for r in qhn if r["set"] == name])}
    report["qhe_rerun_files"] = qh_files
    (RES / f"scale{TAG}" / "compare.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
