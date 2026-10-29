"""Deviation I-25: QLine on Qiskit HumanEval, a corpus of current (Qiskit >= 1.0) programs. Read, never executed.

Per task, the file is the prompt followed by the canonical solution in the standard set, and the canonical solution
alone in the hard set, whose prompt is an English description; the test is not used. The measures are
those of S1 (scale_run.s1_one, unchanged), the I-23 reason for a file with no circuit (coverage_reasons.reason,
unchanged), and the kinds of the interpreter's notes.
Usage (workspace root): python experiments/icpc/qhe_run.py --data-root <data-root>  -> results/icpc/qhe/
"""
import argparse
import csv
import json
import re
import statistics as st
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
from icpc.coverage_reasons import reason  # noqa: E402
from icpc.scale_run import S1_LIMIT, s1_one  # noqa: E402
from tool.corpus.hardlimit import run_all  # noqa: E402

OUT = ROOT / "experiments" / "results" / "icpc" / "qhe"
SETS = {"standard": "dataset_qiskit_test_human_eval.json", "hard": "dataset_qiskit_test_human_eval_hard.json"}


def notes(path: Path):
    """The interpreter's notes, by kind (the note text without line-specific names and numbers)."""
    from tool import srcml as X
    from tool.interp import Interpreter
    try:
        tr = Interpreter(str(path), 60).run(X.parse_file(path))
    except Exception as exc:  # recorded as a result
        return [f"error: {type(exc).__name__}"]
    return [re.sub(r"'[^']*'|\"[^\"]*\"|\b\d+\b|`[^`]*`", "_", m) for _, m in tr.notes]


def one(p: Path, name: str, task: str, difficulty: str):
    r = s1_one(p, p.name)
    return r | {"set": name, "task": task, "difficulty": difficulty,
                "reason": reason(p.read_text()) if r.get("error") == "no circuit" else "", "notes": "|".join(notes(p))}


def timed_out(p: Path, name: str, task: str, difficulty: str):
    return {"file": p.name, "code_lines": 0, "error": "timeout", "set": name, "task": task, "difficulty": difficulty,
            "reason": "", "notes": ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    src = Path(a.data_root) / "qiskit_human_eval"
    files = OUT / "programs"
    files.mkdir(parents=True, exist_ok=True)
    jobs = []
    for name, fn in SETS.items():
        for task in json.load(open(src / fn)):
            k = task["task_id"].split("/")[-1]
            p = files / f"{name}_{int(k):03d}.py"
            p.write_text(task["canonical_solution"] if name == "hard" else task["prompt"] + task["canonical_solution"])
            jobs.append((p, name, task["task_id"], task.get("difficulty_scale", "")))
    rows = list(run_all(one, jobs, S1_LIMIT, timed_out, a.workers))
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(OUT / "tasks.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    summ = {}
    for name in SETS:
        rs = [r for r in rows if r["set"] == name]
        ok = [r for r in rs if not r.get("error")]
        share = [int(x) / r["code_lines"] for r in ok for x in r["slice_lines"].split(";") if x and r["code_lines"]]
        summ[name] = {"tasks": len(rs), "circuit": len(ok),
                      "errors": dict(Counter(r["error"] for r in rs if r.get("error"))),
                      "no_circuit_reasons": dict(Counter(r["reason"] for r in rs if r["reason"])),
                      "by_difficulty": {d: {"tasks": sum(r["difficulty"] == d for r in rs),
                                            "circuit": sum(r["difficulty"] == d for r in ok)}
                                        for d in sorted({r["difficulty"] for r in rs})},
                      "median_ms": round(1000 * st.median(r["t_srcml"] + r["t_interp"] + r["t_slice"] + r["t_srcslice"] + r["t_profile"] for r in ok), 1) if ok else None,
                      "median_ops": st.median(r["ops"] for r in ok) if ok else None,
                      "may_files": sum(r["may_ops"] > 0 for r in ok),
                      "median_slice_share": round(st.median(share), 4) if share else None,
                      "note_kinds": dict(Counter(n for r in rs for n in r["notes"].split("|") if n).most_common(15))}
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
