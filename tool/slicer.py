"""The wire rule (Section 3) on a static operation trace, and the slice in source lines.

An operation reads and writes every qubit it may act on (all candidates of an unresolved qubit argument)
and the classical bits it measures into; a conditioned operation also reads its condition bits. The
backward pass uses reaching definitions for classical bits, and a bit is killed only by a measurement that
certainly writes it (a resolved, unconditional, non-may measurement). Qubit locations are never killed, so
over-approximated operations can only enlarge the slice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Set, Tuple

from tool.gates import NOT_SLICED
from tool.interp import Circuit, Op


@dataclass
class Slice:
    ops: List[int]                       # positions in the circuit's trace
    quantum_lines: Set[int]              # lines whose operations are in the slice (and call sites leading to them)
    classical_lines: Set[int]            # lines computing their qubits, bits, angles, conditions, loops
    iterations: Dict[int, Set[Tuple]]    # line -> iteration vectors of its sliced operations
    may: int = 0                         # sliced operations that are over-approximations

    @property
    def lines(self) -> Set[int]:
        return self.quantum_lines | self.classical_lines


def terminal(circ: Circuit) -> Set[int]:
    """Measurements no later operation depends on: their qubit is not acted on later and their bit is not read
    later (as the study's loader and oracle treat them). The criterion is the state before them."""
    out, touched, read = set(), set(), set()
    for k in range(len(circ.ops) - 1, -1, -1):
        op = circ.ops[k]
        if op.name == "measure" and not (op.touched & touched) and not ({b for s in op.clbits for b in s} & read):
            out.add(k)
        if op.name not in NOT_SLICED:
            touched |= op.touched
            read |= op.cond
    return out


def wire_slice(circ: Circuit, criterion: Iterable[int], rule: str = "wire", keep_terminal: bool = False) -> Slice:
    """rule "wire": every operation reads and writes all its qubits. rule "cpdg": the classical PDG reading, a
    controlled gate writes only its targets (its controls are read). Terminal measurements are left out unless
    keep_terminal is set."""
    needed: Set[Tuple[str, int]] = {("q", q) for q in criterion}
    keep: List[int] = []
    skip = set() if keep_terminal else terminal(circ)
    for k in range(len(circ.ops) - 1, -1, -1):
        op = circ.ops[k]
        if op.name in NOT_SLICED or k in skip:
            continue
        qs = {("q", q) for q in op.touched}
        writes = qs
        if rule == "cpdg" and op.nctrl and len(op.qubits) > op.nctrl:
            writes = {("q", q) for s in op.qubits[op.nctrl:] for q in s}
        cs = {("c", b) for s in op.clbits for b in s} if op.name == "measure" else set()
        if (writes | cs) & needed:
            keep.append(k)
            certain = op.name == "measure" and not op.may and not op.cond and all(len(s) == 1 for s in op.clbits)
            killed = cs if certain else set()
            needed = (needed - killed) | qs | {("c", b) for b in op.cond}
    keep.reverse()
    ql, cl, it = set(), set(), {}
    for k in keep:
        op = circ.ops[k]
        ql.add(op.line)
        ql |= set(op.calls)
        cl |= set(op.deps)
        it.setdefault(op.line, set()).add(op.iters)
    return Slice(keep, ql, cl - ql, it, sum(circ.ops[k].may for k in keep))


@dataclass
class ForwardSlice:
    ops: List[int]                      # positions the start can affect, in trace order (the start included)
    lines: Set[int]                     # their source lines
    iterations: Dict[int, Set[Tuple]]   # line -> iteration vectors of its operations in the slice
    qubits: FrozenSet[int]              # qubits whose final state the start can affect
    bits: FrozenSet[int]                # classical bits whose value the start can affect


def forward_slice(circ: Circuit, start: Iterable[int]) -> ForwardSlice:
    """Forward QDG slice of the operations at positions `start`: every later operation that reads a location
    they can affect, under the same rule as wire_slice (an operation reads and writes all its qubits, a
    measurement writes its bits, a conditioned operation reads its condition bits). By duality, q is in
    .qubits exactly when the start is in the backward slice of q (without terminal-measurement skipping)."""
    start = sorted(set(start))
    if not start:
        return ForwardSlice([], set(), {}, frozenset(), frozenset())
    aff_q: Set[int] = set()
    aff_c: Set[int] = set()
    keep: List[int] = []
    for k in range(start[0], len(circ.ops)):
        op = circ.ops[k]
        if op.name in NOT_SLICED:
            continue
        if k in start or (op.touched & aff_q) or (op.cond & aff_c):
            keep.append(k)
            aff_q |= op.touched
            if op.name == "measure":
                aff_c |= {b for s in op.clbits for b in s}
    it: Dict[int, Set[Tuple]] = {}
    for k in keep:
        it.setdefault(circ.ops[k].line, set()).add(circ.ops[k].iters)
    return ForwardSlice(keep, {circ.ops[k].line for k in keep}, it, frozenset(aff_q), frozenset(aff_c))
