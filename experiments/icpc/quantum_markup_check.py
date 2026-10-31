"""Check of the quantum markup (tool/quantum_markup.py) on every program of the study.

For each file, read as data and never executed:
  lossless   the text of the quantum markup is the file, character for character (only attributes are added);
  reached    every operation of the sliced circuit is counted on a marked call or statement, so no operation the
             layer read is missing from the markup.
Files: our programs (tool/tests), LintQ's corpus, Bugs4Q, the Qiskit textbook, Qiskit HumanEval; the OpenQASM 2
files under 1 MB of the corpora and the OpenQASM 3 examples and round-trip programs.
Usage (workspace root): python experiments/icpc/quantum_markup_check.py --data-root ../qslice-icpc-data [--workers 4]
-> results/icpc/quantum_markup/check.csv, summary.json
"""
import argparse
import csv
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tool.corpus.hardlimit import run_all  # noqa: E402

OUT = ROOT / "experiments" / "results" / "icpc" / "quantum_markup"
LIMIT = 120
MAX_QASM_BYTES = 1_000_000


def one(path: str, corpus: str):
    import xml.etree.ElementTree as ET
    from tool.quantum_markup import markup, to_xml
    row = {"corpus": corpus, "file": path}
    try:
        unit, n = markup(path)
        text = open(path, newline="", errors="replace").read()
        back = "".join(ET.fromstring(to_xml(unit).encode()).itertext())
        return row | {"lossless": back == text, "operations": n["operations"], "reached": n["reached"], "error": ""}
    except Exception as exc:  # recorded: a file the front end rejects, or srcML fails on
        return row | {"error": f"{type(exc).__name__}: {str(exc)[:100]}"}


def timeout(path, corpus):
    return {"corpus": corpus, "file": path, "error": "timeout"}


def files(data_root: Path):
    py = lambda d: sorted(glob.glob(str(d) + "/**/*.py", recursive=True))  # noqa: E731
    yield from (("ours", f) for d in ("programs", "big", "controlflow") for f in py(ROOT / "tool" / "tests" / d))
    for name, d in (("lintq", data_root / "lintq" / "exp_v08" / "files_selected"), ("bugs4q", data_root / "bugs4q"),
                    ("textbook", data_root / "textbook_py"), ("humaneval", data_root / "qiskit_human_eval")):
        yield from ((name, f) for f in py(d))
    seen = set()
    for f in sorted({os.path.realpath(f) for d in ("../qslice-icpc/data", "data")
                     for f in glob.glob(str(ROOT / d) + "/**/*.qasm", recursive=True)}):
        if not os.path.isfile(f) or os.path.getsize(f) > MAX_QASM_BYTES or "openqasm3_roundtrip/corpus" in f:
            continue
        h = open(f, "rb").read()
        if h in seen:                              # the corpora hold copies of the same files
            continue
        seen.add(h)
        yield ("openqasm3" if "openqasm3_" in f else "openqasm", f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    todo = list(files(Path(a.data_root)))
    keys = ["corpus", "file", "lossless", "operations", "reached", "error"]
    rows = []
    with open(OUT / "check.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, keys)
        w.writeheader()
        for k, r in enumerate(run_all(one, [(f, c) for c, f in todo], LIMIT, timeout, a.workers)):
            r["file"] = os.path.relpath(r["file"], ROOT)
            w.writerow(r)
            rows.append(r)
            if k % 500 == 0:
                print(k, "of", len(todo), flush=True)
    summ = {}
    for c in sorted({r["corpus"] for r in rows}):
        sel = [r for r in rows if r["corpus"] == c]
        ok = [r for r in sel if not r["error"]]
        summ[c] = {"files": len(sel), "marked_up": len(ok), "lossless": sum(r["lossless"] is True for r in ok),
                   "with_operations": sum(r["operations"] > 0 for r in ok),
                   "all_reached": sum(r["operations"] > 0 and r["reached"] == r["operations"] for r in ok),
                   "operations": sum(r["operations"] for r in ok), "reached": sum(r["reached"] for r in ok),
                   "errors": len(sel) - len(ok)}
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
