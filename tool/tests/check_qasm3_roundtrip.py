"""The OpenQASM 3 layer on the round-trip corpus (experiments/icpc/oq3_export_corpus.py).
  ours    each exported program's trace equals the trace the Qiskit front end builds for the same Python program:
          operation names, qubits, bits written, condition bits and may-operations (loop iterations of the Python
          source are not in the exported program, which Qiskit has already unrolled);
  corpus  each re-exported OpenQASM 2 file's trace equals the circuit Qiskit loaded: names and qubits in order,
          barriers left out (tool.tests.check_trace.flat).
Usage (workspace root): python -m tool.tests.check_qasm3_roundtrip [ours|corpus] [-v]
-> experiments/results/icpc/qasm3_srcml/roundtrip_<set>.csv"""
import csv
import json
import sys
from pathlib import Path

from tool import qasm3_layer

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "openqasm3_roundtrip"
OUT = ROOT / "experiments" / "results" / "icpc" / "qasm3_srcml"
NAME = {"U": "u"}


def mine(path, full):
    out = []
    for o in qasm3_layer.ops(path):
        if o.name == "barrier":                        # never sliced; the Qiskit front end leaves them out
            continue
        q = [sorted(s) for s in o.qubits]
        if full:
            out.append((NAME.get(o.name, o.name), q, [sorted(s) for s in o.clbits], sorted(o.cond), o.may))
        else:
            out.append((NAME.get(o.name, o.name), [x[0] for x in q]))
    return out


def theirs(ans, full):
    if full:
        return [(o["name"], o["qubits"], o["clbits"], o["cond"], o["may"]) for o in ans["ops"]]
    return [(n, list(q)) for n, q in ans["flat"] if n != "barrier"]


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "ours"
    verbose = "-v" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    rows, ok = [], 0
    for f in sorted((DATA / which).glob("*.qasm")):
        ans = json.load(open(f.with_suffix(".json")))
        full = which == "ours"
        try:
            a, b = mine(f, full), theirs(ans, full)
            same = a == b
            note = ""
            if not same:
                k = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
                note = f"op {k}: layer {a[k] if k < len(a) else None} answer {b[k] if k < len(b) else None} ({len(a)} vs {len(b)})"
        except Exception as e:
            same, note = False, f"{type(e).__name__}: {str(e)[:160]}"
        ok += same
        rows.append([f.name, same, note])
        if verbose and not same:
            print("DIFF", f.name, note)
    with open(OUT / f"roundtrip_{which}.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "equal", "note"])
        w.writerows(rows)
    print(f"{which}: {ok} of {len(rows)} equal")


if __name__ == "__main__":
    main()
