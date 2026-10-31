"""Quantum markup: the program's srcML with what the quantum layer reads in it, as attributes in a namespace of its own.

srcML's markup of a Qiskit program is the markup of any Python program; a gate is a call like any other. The layer
(E1, E2) knows which calls are gates, which of their arguments are qubits, and which operations each adds to the
circuit. This module writes that into the markup, so another srcML tool can read the quantum roles without
reimplementing the layer:

  <call qu:role="gate" qu:gate="cx" qu:ops="3" qu:qubits="0-3">   a call that adds operations (role below)
  <argument qu:arg="control">                                        control, target, qubit, clbit, angle (E1)

  qu:role     gate, measure, reset, barrier   a role-table method; for OpenQASM the statement kind
              compose                          append, compose, measure_all: operations mapped onto the circuit
              call                             a call of a function whose body adds operations
              control                          if_test, while_loop, for_loop, switch, case, else_
              circuit, qreg, creg              QuantumCircuit, QuantumRegister (AncillaRegister), ClassicalRegister
  qu:ops      operations the call adds to the sliced circuit, over every iteration (E2)
  qu:qubits   the qubits they act on, clbits the bits they write, cond the bits a condition reads, as ranges "0-3 5"
  qu:may      "yes" when one of them is a may-operation (an unknown condition, loop or qubit index)

The sliced circuit is the one tool.cli slices by default, the circuit with most operations; a gate on another
circuit has its role but no counts unless that circuit is composed into it. Two calls of the same method on one line
share their counts. Only attributes are added: the text of the markup is the program, character for character.
Usage: python -m tool.quantum_markup PROGRAM.py|CIRCUIT.qasm [-o OUT.xml]   (installed: qiskit2srcml; qasm2srcml --layer)
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from tool import srcml as X
from tool.gates import GATES

QU = "http://www.srcML.org/srcML/quantum"
A = "{%s}" % QU
CONSTRUCTORS = {"QuantumCircuit": "circuit", "QuantumRegister": "qreg", "AncillaRegister": "qreg",
                "ClassicalRegister": "creg"}
COMPOSE = {"append", "compose", "measure_all", "measure_active"}
FLOW = {"if_test", "while_loop", "for_loop", "switch", "case", "else_"}
KINDS = {"measure": "measure", "measure_all": "measure", "measure_active": "measure", "reset": "reset",
         "barrier": "barrier"}
OQ_TAGS = {"measure": "measure", "reset": "reset", "barrier": "barrier"}


def ranges(xs: Iterable[int]) -> str:
    xs, out = sorted(set(xs)), []
    for x in xs:
        if out and x == out[-1][1] + 1:
            out[-1][1] = x
        else:
            out.append([x, x])
    return " ".join(str(a) if a == b else f"{a}-{b}" for a, b in out)


def _set_counts(e: ET.Element, ops: List) -> None:
    e.set(A + "ops", str(len(ops)))
    for key, bits in (("qubits", [q for o in ops for s in o.qubits for q in s]),
                      ("clbits", [b for o in ops for s in o.clbits for b in s]),
                      ("cond", [b for o in ops for b in o.cond])):
        if bits:
            e.set(A + key, ranges(bits))
    if any(o.may for o in ops):
        e.set(A + "may", "yes")


def _method(call: ET.Element) -> str:
    """The name a call ends with: cx in qc.cx(..), QuantumCircuit in qiskit.QuantumCircuit(..)."""
    n = X.child(call, "name")
    if n is None:
        return ""
    parts = X.children(n, "name")
    return X.text(parts[-1] if parts else n).strip()


def _arguments(call: ET.Element, name: str) -> None:
    sig = GATES.get(name)
    al = X.child(call, "argument_list")
    if sig is None or al is None:
        return
    kinds = dict(sig.args)
    for i, arg in enumerate(X.children(al, "argument")):
        kw = X.child(arg, "name")
        pname = X.text(kw).strip() if kw is not None and arg.find(X.S + "expr") is not None else None
        if pname is None:
            if i >= len(sig.args):
                continue
            pname = sig.args[i][0]
        k = kinds.get(pname)
        role = {"c": "clbit", "angle": "angle"}.get(k)
        if k == "q":
            role = "control" if pname.startswith("control") else "target" if pname.startswith("target") else "qubit"
        if role:
            arg.set(A + "arg", role)


def annotate_python(unit: ET.Element, trace, circ) -> Dict[str, int]:
    """Mark the calls of a Qiskit program's srcML (in place). Returns how many operations of the sliced circuit
    reached a marked call, for the check that none is left out."""
    named = {(o.line, o.name) for c in trace.circuits for o in c.ops}
    sites = {l for c in trace.circuits for o in c.ops for l in o.calls}
    direct, via = defaultdict(list), defaultdict(list)
    for o in (circ.ops if circ else []):
        direct[o.line].append(o)
        for l in o.calls:
            via[l].append(o)
    reached, unmarked = set(), defaultdict(list)
    for call in unit.iter(X.S + "call"):
        ln, m = X.line(call), _method(call)
        role = CONSTRUCTORS.get(m)
        ops: Optional[List] = None
        if role is None and m in FLOW:
            role = "control"
        elif role is None and m in COMPOSE and (direct[ln] or via[ln]):
            # append(gate, qubits) adds an operation named by its gate, at this line; compose maps a circuit's
            # operations here, which keep the lines that made them and record this call site
            role = "compose" if m in ("append", "compose") else "measure"
            ops = [o for o in direct[ln] if o.name == "measure" or m == "append"] + via[ln]
        elif role is None and (ln, m) in named:
            role = KINDS.get(m, "gate")
            ops = [o for o in direct[ln] if o.name == m]
            _arguments(call, m)
        elif role is None and ln in sites:
            role = "call"
            ops = via[ln]
        if role is None:
            unmarked[ln].append(call)
            continue
        call.set(A + "role", role)
        if role in ("gate", "measure", "reset", "barrier") and m not in COMPOSE:
            call.set(A + "gate", m)
        if ops is not None:
            _set_counts(call, ops)
            reached.update(map(id, ops))
    # a gate whose method the source names only at run time, as in getattr(qc, gate)(theta, q): the operations of
    # its line no marked call accounts for go to the line's outermost unmarked call
    for ln, calls in unmarked.items():
        left = [o for o in direct[ln] if id(o) not in reached]
        if left:
            calls[0].set(A + "role", "gate")
            calls[0].set(A + "gate", " ".join(sorted({o.name for o in left})))
            _set_counts(calls[0], left)
            reached.update(map(id, left))
    return {"operations": len(circ.ops) if circ else 0, "reached": sum(id(o) in reached for o in circ.ops) if circ else 0}


def annotate_qasm(unit: ET.Element, trace) -> Dict[str, int]:
    """Mark the operation statements of an OpenQASM program's srcML (in place). Gate calls, measure, reset and
    barrier, whose kind the markup already states, and subroutine calls get the operations the layer read from them."""
    circ = trace.main_circuit()
    by = defaultdict(list)
    for o in circ.ops:
        by[o.line].append(o)
    per_line = defaultdict(list)
    for e in unit.iter():
        t = X.tag(e)
        if t in OQ_TAGS:
            per_line[X.line(e)].append((e, OQ_TAGS[t], t))
        elif t == "call":
            name = _method(e)
            if e.find(X.S + "argument_list[@type='quantum']") is not None:
                per_line[X.line(e)].append((e, "gate", name))
            elif any(o.name == name for o in by.get(X.line(e), ())):
                per_line[X.line(e)].append((e, "call", name))     # a subroutine: one operation on its qubits
    reached = set()
    for ln, items in per_line.items():
        mine = defaultdict(list)
        for o in by.get(ln, ()):
            k = next((k for k, (_, role, name) in enumerate(items) if o.name in (name, role)), None)
            # an operation no statement names (a modifier, ctrl @ x, is named by what it applies) goes to the
            # line's first statement
            mine[0 if k is None else k].append(o)
        for k, (e, role, name) in enumerate(items):
            e.set(A + "role", role)
            if role in ("gate", "call"):
                e.set(A + "gate", name)
            _set_counts(e, mine[k])
            reached.update(map(id, mine[k]))
    return {"operations": len(circ.ops), "reached": sum(id(o) in reached for o in circ.ops)}


def _register():
    ET.register_namespace("", X.NS)
    ET.register_namespace("pos", X.POS)
    ET.register_namespace("qu", QU)


def to_xml(unit: ET.Element) -> str:
    _register()
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + ET.tostring(unit, encoding="unicode") + "\n"


def markup(path) -> Tuple[ET.Element, Dict[str, int]]:
    """The quantum markup of a Qiskit program or an OpenQASM 2 or 3 file, and the operations it reached."""
    path = Path(path)
    if path.suffix == ".qasm":
        from tool import qasm  # noqa: PLC0415
        text = path.read_text(errors="replace")
        if qasm.openqasm_version(text) == 3:
            from tool import qasm3_layer  # noqa: PLC0415
            from tool.qasm3_srcml import to_srcml  # noqa: PLC0415
            trace = qasm3_layer.read(path)
        else:
            from tool.qasm_srcml import to_srcml  # noqa: PLC0415
            trace = qasm.read(path)
        unit = ET.fromstring(to_srcml(open(path, newline="", errors="replace").read(), str(path)).encode())
        return unit, annotate_qasm(unit, trace)
    from tool.interp import Interpreter  # noqa: PLC0415
    unit = X.parse_file(path)
    trace = Interpreter(str(path)).run(unit)
    return unit, annotate_python(unit, trace, trace.main_circuit())


def qasm_main(argv=None) -> int:
    """qasm2srcml: an OpenQASM 2 or 3 file in srcML, Behler et al.'s markup; --layer adds the quantum layer's
    attributes, as qiskit2srcml does."""
    ap = argparse.ArgumentParser(prog="qasm2srcml", description="OpenQASM 2 or 3 in srcML (Behler et al.'s markup)")
    ap.add_argument("program")
    ap.add_argument("-o", "--output")
    ap.add_argument("--layer", action="store_true", help="add the operations the quantum layer reads (qu: attributes)")
    a = ap.parse_args(argv)
    if a.layer:
        unit, _ = markup(a.program)
        out = to_xml(unit)
    else:
        from tool import qasm  # noqa: PLC0415
        text = open(a.program, newline="", errors="replace").read()
        if qasm.openqasm_version(text) == 3:
            from tool.qasm3_srcml import to_srcml  # noqa: PLC0415
        else:
            from tool.qasm_srcml import to_srcml  # noqa: PLC0415
        out = to_srcml(text, a.program) + "\n"
    if a.output:
        Path(a.output).write_text(out)
    else:
        sys.stdout.write(out)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="qiskit2srcml",
                                 description="srcML of a Qiskit or OpenQASM program with the quantum layer's roles")
    ap.add_argument("program")
    ap.add_argument("-o", "--output")
    a = ap.parse_args(argv)
    unit, _ = markup(a.program)
    out = to_xml(unit)
    if a.output:
        Path(a.output).write_text(out)
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
