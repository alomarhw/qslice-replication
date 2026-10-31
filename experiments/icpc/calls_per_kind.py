"""Programs of LintQ's corpus that call each kind of method, for the role table of Section V (descriptive).

One rule for every row: a program counts for a kind if its text calls a method of that kind as `.name(`, or, for
the function circuit_to_dag, as `name(`. The kinds are
the categories of tool.gates (Qiskit 2.3 gates by qubit count, methods removed in Qiskit 1.0, special forms) and the
calls handled outside the table. Files are read, never executed.
Usage (workspace root): python experiments/icpc/calls_per_kind.py --data-root <data-root>
  -> results/icpc/unmodelled/calls_per_kind.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tool import gates as G  # noqa: E402

OUT = ROOT / "experiments" / "results" / "icpc" / "unmodelled"


def kinds():
    fq = G._from_qiskit()
    plural = {"qubits", "control_qubits", "target_qubits", "qargs", "ancilla_qubits"}
    one, two, multi = set(), set(), set()
    for n, s in fq.items():
        qn = [p for p, k in s.args if k == "q"]
        if len(qn) == 1 and not set(qn) & plural:
            one.add(n)
        elif len(qn) == 2 and not set(qn) & plural:
            two.add(n)
        else:
            multi.add(n)
    multi.discard("noop")  # a directive, never sliced: counted with barrier and delay (2026-11-01; no program calls it)
    legacy = set(G._legacy()) - set(fq) - set(G._special())
    return {"single": one, "two": two, "multi": multi, "legacy": legacy, "special": set(G._special()) | {"noop"},
            "composition": {"append", "compose", "measure_all", "measure_active"},
            "control_flow": {"if_test", "while_loop", "for_loop", "switch", "c_if"},
            "transform": {"inverse", "power", "repeat", "reverse_ops", "assign_parameters", "bind_parameters"},
            "to_dag": {"circuit_to_dag"}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    files = sorted((Path(ap.parse_args().data_root) / "lintq" / "exp_v08" / "files_selected").glob("*.py"))
    K = kinds()
    # methods are called as .name(; the DAG conversion is a function, called as name( or module.name(
    pats = {k: re.compile((r"\b(" if k == "to_dag" else r"\.(") + "|".join(sorted(map(re.escape, v))) + r")\s*\(")
            for k, v in K.items()}
    counts = {k: 0 for k in K}
    for f in files:
        text = f.read_text(errors="replace")
        for k, pat in pats.items():
            counts[k] += bool(pat.search(text))
    out = {"programs": len(files), "per_kind": counts, "methods": {k: sorted(v) for k, v in K.items()}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "calls_per_kind.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({"programs": len(files), "per_kind": counts}, indent=1))


if __name__ == "__main__":
    main()
