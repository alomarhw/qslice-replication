"""Rerun after the gate-table correction of 2026-10-29: five QuantumCircuit methods that take qubits but add no
operation (from_instructions, if_else, qubit_duration, qubit_start_time, qubit_stop_time) left the role table. Only
files that call them can trace differently; their S1 rows are recomputed with scale_run.s1_one (unchanged) and
written, with every other row copied, to results/icpc/scale__rerun-20261029/. The old results stay in place.
Usage (workspace root): python experiments/icpc/rerun_gate_table.py --data-root <data-root>
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
from icpc.rerun_controlflow_files import stats, write  # noqa: E402
from icpc.scale_run import s1_one  # noqa: E402

RES = ROOT / "experiments" / "results" / "icpc"
CALLS = re.compile(r"\.(from_instructions|if_else|qubit_duration|qubit_start_time|qubit_stop_time)\(")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    corpus = Path(ap.parse_args().data_root) / "lintq" / "exp_v08" / "files_selected"
    s1 = list(csv.DictReader(open(RES / "scale" / "s1_lintq.csv")))
    out, hit = [], []
    for r in s1:
        if CALLS.search((corpus / r["file"]).read_text(errors="replace")):
            n = s1_one(corpus / r["file"], r["file"])
            out.append({**{k: "" for k in r}, **n})
            hit.append({"file": r["file"], "old_ops": r.get("ops"), "new_ops": n.get("ops"),
                        "old_slice_lines": r.get("slice_lines"), "new_slice_lines": n.get("slice_lines")})
        else:
            out.append(r)
    write(RES / "scale__rerun-20261029" / "s1_lintq.csv", out)
    rep = {"rerun_files": hit, "old": stats(s1), "new": stats(out)}
    (RES / "scale__rerun-20261029" / "compare.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
