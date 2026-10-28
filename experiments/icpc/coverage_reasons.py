"""Deviation I-23: why the S1 files of LintQ's corpus that yield no circuit do not, by a fixed rule on the file text
(the files are read, never executed).
  no-construction   the text never calls QuantumCircuit(
  from-file-or-lib  it builds circuits only from a file or library (from_qasm, qasm2.load, QuantumCircuit.from_,
                    or transpile( without any gate call on a circuit)
  other             the rest: circuits built in code the interpreter does not follow, or reached only through
                    unknown calls
Usage (workspace root): python experiments/icpc/coverage_reasons.py --data-root <data-root>
  -> results/icpc/scale/coverage_reasons.csv, coverage_reasons.json
"""
import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experiments" / "results" / "icpc" / "scale"
GATE_CALL = re.compile(r"\.\s*(h|x|y|z|cx|cz|ry|rz|rx|u|u3|ccx|swap|measure|cp|crz|s|t|sdg|tdg|mcx)\s*\(")


def reason(text: str) -> str:
    if "QuantumCircuit(" not in text:
        return "no-construction"
    if re.search(r"from_qasm|qasm2\.load|QuantumCircuit\.from_", text) or ("transpile(" in text and not GATE_CALL.search(text)):
        return "from-file-or-lib"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    a = ap.parse_args()
    corpus = Path(a.data_root) / "lintq" / "exp_v08" / "files_selected"
    rows = []
    for r in csv.DictReader(open(OUT / "s1_lintq.csv")):
        if r["error"] != "no circuit":
            continue
        rows.append({"file": r["file"], "reason": reason((corpus / r["file"]).read_text(errors="replace"))})
    with open(OUT / "coverage_reasons.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "reason"])
        w.writeheader()
        w.writerows(rows)
    c = Counter(r["reason"] for r in rows)
    (OUT / "coverage_reasons.json").write_text(json.dumps({"no_circuit_files": len(rows), **c}, indent=1) + "\n")
    print(len(rows), dict(c))


if __name__ == "__main__":
    main()
