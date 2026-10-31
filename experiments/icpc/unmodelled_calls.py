"""Deviation I-27: which calls the static interpreter does not model, and how often, per corpus (descriptive).

Every program is read and interpreted, never executed. From the interpreter's notes, each program contributes at most
once to each kind: a QuantumCircuit method that is not modelled, a method whose result is treated as unknown, a
conversion of a circuit to a DAG, and a circuit passed to a function or method the interpreter cannot see.
Usage (workspace root): python experiments/icpc/unmodelled_calls.py --data-root <data-root>
  -> results/icpc/unmodelled/{programs.csv, summary.json}
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tool.corpus.hardlimit import run_all  # noqa: E402

OUT = ROOT / "experiments" / "results" / "icpc" / "unmodelled"
RES = ROOT / "experiments" / "results" / "icpc"
LIMIT = 120
PATTERNS = {
    "method_not_modelled": re.compile(r"QuantumCircuit\.(\w+) is not modelled"),
    "result_unknown": re.compile(r"QuantumCircuit\.(\w+): result treated as unknown"),
    "to_dag": re.compile(r"(\w+): the circuit is converted to a DAG"),
    "circuit_to_unseen_code": re.compile(r"a circuit is passed to a (function|method) the tool cannot see"),
}


def one(path: Path, corpus: str, rel: str):
    from tool import srcml as X
    from tool.interp import Interpreter
    try:
        tr = Interpreter(str(path), LIMIT).run(X.parse_file(path))
        notes = [m for _, m in tr.notes]
        circuit = int(bool(tr.main_circuit() and tr.main_circuit().ops))
        err = ""
    except Exception as exc:  # recorded as a result
        notes, circuit, err = [], 0, type(exc).__name__
    found = {}
    for kind, pat in PATTERNS.items():
        hits = sorted({m.group(1) for n in notes for m in [pat.search(n)] if m})
        found[kind] = ";".join(hits)
    return {"corpus": corpus, "file": rel, "circuit": circuit, "error": err, **found}


def timed_out(path, corpus, rel):
    return {"corpus": corpus, "file": rel, "circuit": 0, "error": "timeout", **{k: "" for k in PATTERNS}}


def summarize(rows):
    """The summary of the programs' rows, as run results or as read back from programs.csv."""
    rows = [{**r, "circuit": int(r["circuit"]) if str(r["circuit"]).isdigit() else int(r["circuit"] in (True, "True"))}
            for r in rows]
    summ = {}
    for corpus in ("lintq", "textbook", "bugs4q", "qhe"):
        rs = [r for r in rows if r["corpus"] == corpus]
        summ[corpus] = {"programs": len(rs), "with_circuit": sum(r["circuit"] for r in rs),
                        "errors": dict(Counter(r["error"] for r in rs if r["error"]))}
        for kind in PATTERNS:
            if kind == "circuit_to_unseen_code":
                summ[corpus][kind] = sum(bool(r[kind]) for r in rs)
            else:
                c = Counter(m for r in rs for m in r[kind].split(";") if m)
                summ[corpus][kind] = {"programs": sum(bool(r[kind]) for r in rs), "top": c.most_common(12)}
    return summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--workers", type=int, default=4)
    root = Path(ap.parse_args().data_root)
    a = ap.parse_args()
    jobs = [(p, "lintq", p.name) for p in sorted((root / "lintq" / "exp_v08" / "files_selected").glob("*.py"))]
    for name, csv_path in (("bugs4q", RES / "tool_acceptance" / "tool-v7" / "t3_bugs4q.csv"),
                           ("textbook", RES / "tool_coverage" / "textbook_v7.csv")):
        for r in csv.DictReader(open(csv_path)):
            if r["uses_qiskit"] == "1":
                f = Path(r["file"].replace("<data-root>", str(root)))
                jobs.append((f, name, str(f.relative_to(root))))
    jobs += [(p, "qhe", p.name) for p in sorted((RES / "qhe" / "programs").glob("standard_*.py"))]
    rows = list(run_all(one, jobs, LIMIT, timed_out, a.workers))
    OUT.mkdir(parents=True, exist_ok=True)
    keys = ["corpus", "file", "circuit", "error"] + list(PATTERNS)
    with open(OUT / "programs.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["corpus"], r["file"])))
    summ = summarize(rows)
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
