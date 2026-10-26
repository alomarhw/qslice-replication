"""Qubit slice profiles (Deviation I-17): the srcSlice-style profile of one qubit, from the static trace and srcML.

For qubit q of a traced circuit:
  defs_uses     lines of the operations that act on q (under the QDG every such operation reads and writes q)
  names         distinct source expressions that denote q alone in gate calls (e.g. qr[0], q, qubit), read from the
                srcML argument of each qubit parameter (tool.gates); calls with keyword arguments are skipped
  functions     call-site lines of the functions inside which q is acted on (Op.calls)
  dependents    other qubits whose final state q's first operation can affect (forward QDG slice)
  bits          classical bits measured from q, and lines of operations conditioned on them
  backward/forward  lines of q's backward slice (state at the end) and of the forward slice from its first operation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set

from tool import srcml as X
from tool.gates import GATES
from tool.interp import Circuit
from tool.slicer import forward_slice, wire_slice


@dataclass
class QubitProfile:
    qubit: int
    defs_uses: Set[int] = field(default_factory=set)
    names: Set[str] = field(default_factory=set)
    functions: Set[int] = field(default_factory=set)
    dependents: Set[int] = field(default_factory=set)
    bits: Set[int] = field(default_factory=set)
    conditioned_lines: Set[int] = field(default_factory=set)
    backward_lines: Set[int] = field(default_factory=set)
    forward_lines: Set[int] = field(default_factory=set)


def qubit_arg_texts(path: Path) -> Dict[int, List[List[str]]]:
    """line -> for each gate call on that line, the source text of its qubit arguments, in parameter order."""
    out: Dict[int, List[List[str]]] = {}
    for call in X.parse_file(path).iter(X.S + "call"):
        name_el, al = call.find(X.S + "name"), call.find(X.S + "argument_list")
        if name_el is None or al is None:
            continue
        name = X.text(name_el).split(".")[-1].strip()
        if name not in GATES:
            continue
        texts = [X.text(a).strip() for a in al.findall(X.S + "argument")]
        if any("=" in t.split("[")[0] for t in texts):
            continue
        out.setdefault(X.line(call), []).append([t for t, k in zip(texts, GATES[name].kinds()) if k == "q"])
    return out


def slice_profile(circ: Circuit, q: int, args: Dict[int, List[List[str]]]) -> QubitProfile:
    p = QubitProfile(q)
    on = [k for k, op in enumerate(circ.ops) if q in op.touched and op.name not in ("barrier", "delay")]
    for k in on:
        op = circ.ops[k]
        p.defs_uses.add(op.line)
        p.functions |= set(op.calls)
        for i, s in enumerate(op.qubits):
            if s == frozenset({q}):
                for texts in args.get(op.line, []):
                    if i < len(texts) and texts[i]:
                        p.names.add(texts[i])
        if op.name == "measure":
            p.bits |= {b for s in op.clbits for b in s}
    p.conditioned_lines = {op.line for op in circ.ops if op.cond & p.bits}
    if on:
        f = forward_slice(circ, [on[0]])
        p.dependents = set(f.qubits) - {q}
        p.forward_lines = f.lines
    p.backward_lines = wire_slice(circ, [q]).quantum_lines
    return p
