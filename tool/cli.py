"""Command line: slice a Qiskit program without running it.

  python -m tool.cli PROGRAM.py --qubits 0,2          criterion: global qubit indices of the main circuit
  python -m tool.cli PROGRAM.py --qubits q[1],anc[0]  criterion: register bits
  python -m tool.cli PROGRAM.py --qubits all --json   one slice per qubit, as JSON
  python -m tool.cli PROGRAM.py --trace               print the operation trace
Options: --circuit NAME (variable name of the circuit to slice; default: the circuit with most operations),
         --annotate (print the source with the slice marked: Q quantum line, C classical line).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from tool.interp import Circuit, Interpreter
from tool import srcml as X
from tool.slicer import wire_slice


def pick_circuit(interp: Interpreter, trace, name):
    if name:
        got = interp.globals.get(name)
        if got and isinstance(got[0], Circuit):
            return got[0]
        sys.exit(f"no circuit named {name}")
    return trace.main_circuit()


def parse_criterion(circ: Circuit, spec: str):
    if spec == "all":
        return [[q] for q in range(circ.n("q"))]
    out = []
    for tok in spec.split(","):
        tok = tok.strip()
        m = re.fullmatch(r"(\w+)\[(\d+)\]", tok)
        if m:
            reg = next((r for r in circ.qregs if r.name == m.group(1)), None)
            if reg is None:
                sys.exit(f"no register {m.group(1)}")
            out.append(circ.offset(reg) + int(m.group(2)))
        else:
            out.append(int(tok))
    return [out]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("program")
    ap.add_argument("--qubits", default="all")
    ap.add_argument("--circuit")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--annotate", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    unit = X.parse_file(Path(a.program))
    t1 = time.perf_counter()
    interp = Interpreter(a.program)
    trace = interp.run(unit)
    t2 = time.perf_counter()
    circ = pick_circuit(interp, trace, a.circuit)
    if circ is None:
        print(json.dumps({"program": a.program, "error": "no circuit found", "notes": trace.notes}))
        return 1
    if a.trace:
        for k, op in enumerate(circ.ops):
            qs = ",".join("q" + ("".join(map(str, sorted(s))) if len(s) == 1 else "{" + ",".join(map(str, sorted(s))) + "}") for s in op.qubits)
            print(f"{k:4d} L{op.line:<4d} {op.name:10s} {qs:20s} {'may ' if op.may else ''}{'if c' + str(sorted(op.cond)) if op.cond else ''}")
    res = []
    for crit in parse_criterion(circ, a.qubits):
        s = wire_slice(circ, crit)
        res.append({"criterion": crit, "operations": len(s.ops), "of": len(circ.ops), "may_operations": s.may,
                    "quantum_lines": sorted(s.quantum_lines), "classical_lines": sorted(s.classical_lines),
                    "iterations": {str(l): sorted(map(list, v)) for l, v in s.iterations.items() if any(v)}})
    t3 = time.perf_counter()
    out = {"program": a.program, "qubits": circ.n("q"), "operations": len(circ.ops), "circuits": len(trace.circuits),
           "notes": [f"line {l}: {m}" for l, m in trace.notes],
           "seconds": {"srcml": round(t1 - t0, 4), "interpret": round(t2 - t1, 4), "slice": round(t3 - t2, 4)},
           "slices": res}
    if a.json:
        print(json.dumps(out, indent=1))
    elif a.annotate:
        src = Path(a.program).read_text().splitlines()
        s = res[0]
        for i, ln in enumerate(src, 1):
            mark = "Q" if i in s["quantum_lines"] else "C" if i in s["classical_lines"] else " "
            print(f"{mark} {i:4d}  {ln}")
    else:
        for r in res:
            print(f"criterion {r['criterion']}: {r['operations']}/{len(circ.ops)} operations; quantum lines "
                  f"{r['quantum_lines']}; classical lines {r['classical_lines']}")
        for n in out["notes"]:
            print("note:", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
