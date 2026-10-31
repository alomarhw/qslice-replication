"""Command line: slice a Qiskit program without running it.

  python -m tool.cli PROGRAM.py --qubits 0,2          criterion: global qubit indices of the main circuit
  python -m tool.cli PROGRAM.py --qubits q[1],anc[0]  criterion: register bits
  python -m tool.cli PROGRAM.py --qubits all --json   one slice per qubit, as JSON
  python -m tool.cli PROGRAM.py --trace               print the operation trace
  python -m tool.cli CIRCUIT.qasm --qubits 0          an OpenQASM 2 or 3 file, through its front end (tool.qasm)
Options: --circuit NAME (variable name of the circuit to slice; default: the circuit with most operations),
         --annotate (print the source with the slice marked: Q quantum line, C classical line),
         --classical srcslice|interp (where classical lines come from: srcSlice's profiles, the default since
         Deviation I-21, or the interpreter's provenance; srcSlice falls back to the interpreter if it is missing).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
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
    ap.add_argument("--forward", type=int, metavar="LINE",
                    help="forward slice from the operations created at source line LINE")
    ap.add_argument("--profile", action="store_true", help="slice profile of each criterion qubit")
    ap.add_argument("--classical", choices=["srcslice", "interp"], default="srcslice")
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    is_qasm = a.program.endswith(".qasm")
    if is_qasm:
        from tool import qasm  # noqa: PLC0415
        unit, t1 = None, time.perf_counter()
        if qasm.openqasm_version(Path(a.program).read_text(errors="replace")) == 3:
            from tool import qasm3_layer  # noqa: PLC0415
            trace = qasm3_layer.read(a.program)
        else:
            trace = qasm.read(a.program)
        circ = trace.main_circuit()
        a.classical = "interp"  # an OpenQASM operation's classical lines are its register declarations
    else:
        unit = X.parse_file(Path(a.program))
        t1 = time.perf_counter()
        interp = Interpreter(a.program)
        trace = interp.run(unit)
        circ = pick_circuit(interp, trace, a.circuit)
    t2 = time.perf_counter()
    if circ is None:
        print(json.dumps({"program": a.program, "error": "no circuit found", "notes": trace.notes}))
        return 1
    if a.trace:
        for k, op in enumerate(circ.ops):
            qs = ",".join("q" + ("".join(map(str, sorted(s))) if len(s) == 1 else "{" + ",".join(map(str, sorted(s))) + "}") for s in op.qubits)
            print(f"{k:4d} L{op.line:<4d} {op.name:10s} {qs:20s} {'may ' if op.may else ''}{'if c' + str(sorted(op.cond)) if op.cond else ''}")
    res = []
    prof = None
    if a.classical == "srcslice":
        from tool import srcslice as SS  # noqa: PLC0415
        if shutil.which(SS.SRCSLICE):
            prof, _ = SS.profiles(Path(a.program))
        else:
            trace.notes.append((0, "srcslice not found: classical lines from the interpreter"))
    for crit in parse_criterion(circ, a.qubits):
        s = wire_slice(circ, crit)
        cl = SS.classical_lines(Path(a.program), s.quantum_lines, prof, unit) if prof is not None else s.classical_lines
        res.append({"criterion": crit, "operations": len(s.ops), "of": len(circ.ops), "may_operations": s.may,
                    "quantum_lines": sorted(s.quantum_lines), "classical_lines": sorted(cl),
                    "classical_lines_interpreter": sorted(s.classical_lines),
                    "iterations": {str(l): sorted(map(list, v)) for l, v in s.iterations.items() if any(v)}})
    if a.forward is not None:
        from tool.slicer import forward_slice  # noqa: PLC0415
        start = [k for k, op in enumerate(circ.ops) if op.line == a.forward]
        f = forward_slice(circ, start)
        res.append({"forward_from_line": a.forward, "operations": len(f.ops), "lines": sorted(f.lines),
                    "qubits": sorted(f.qubits), "bits": sorted(f.bits)})
    if a.profile:
        from tool.profile import qubit_arg_texts, slice_profile  # noqa: PLC0415
        args = {} if is_qasm else qubit_arg_texts(Path(a.program))
        for crit in parse_criterion(circ, a.qubits):
            for q in crit:
                p = slice_profile(circ, q, args)
                res.append({"profile_of_qubit": q, "defs_uses": sorted(p.defs_uses), "names": sorted(p.names),
                            "function_call_sites": sorted(p.functions), "dependent_qubits": sorted(p.dependents),
                            "bits": sorted(p.bits), "conditioned_lines": sorted(p.conditioned_lines),
                            "backward_lines": sorted(p.backward_lines), "forward_lines": sorted(p.forward_lines)})
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
            if "criterion" in r:
                print(f"criterion {r['criterion']}: {r['operations']}/{len(circ.ops)} operations; quantum lines "
                      f"{r['quantum_lines']}; classical lines {r['classical_lines']}")
            else:
                print(json.dumps(r))
        for n in out["notes"]:
            print("note:", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
