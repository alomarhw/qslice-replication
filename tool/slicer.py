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
        elif op.name == "measure" and not op.may and not op.cond and all(len(s) == 1 for s in op.clbits):
            aff_c -= {b for s in op.clbits for b in s}  # certainly overwritten by a value the start cannot affect, as in wire_slice
    it: Dict[int, Set[Tuple]] = {}
    for k in keep:
        it.setdefault(circ.ops[k].line, set()).add(circ.ops[k].iters)
    return ForwardSlice(keep, {circ.ops[k].line for k in keep}, it, frozenset(aff_q), frozenset(aff_c))


# ---- compact traces (tool.qasm.Compact): the same rule on flat arrays, for circuits with millions of operations ----

def compact_terminal(c) -> Set[int]:
    """As terminal(): measurements whose qubit no later operation acts on and whose bit no later condition reads."""
    out, touched, read = set(), set(), set()
    for k in range(len(c) - 1, -1, -1):
        qs = c.qs[c.qoff[k]:c.qoff[k + 1]]
        if c.kind[k] == 1 and not (set(qs) & touched) and c.mbit[k] not in read:
            out.add(k)
        if c.kind[k] != 3:
            touched.update(qs)
            read.update(c.cs[c.coff[k]:c.coff[k + 1]])
    return out


def compact_slice(c, criterion: Iterable[int], term: Set[int] = None) -> List[int]:
    """wire_slice on a compact trace: positions of the QDG slice of the criterion qubits, terminal measurements left
    out."""
    nq, nb = set(criterion), set()
    term = compact_terminal(c) if term is None else term
    keep = []
    for k in range(len(c) - 1, -1, -1):
        if c.kind[k] == 3 or k in term:
            continue
        qs = c.qs[c.qoff[k]:c.qoff[k + 1]]
        mb = c.mbit[k]
        if any(q in nq for q in qs) or (mb >= 0 and mb in nb):
            keep.append(k)
            cond = c.cs[c.coff[k]:c.coff[k + 1]]
            if mb >= 0 and not cond:
                nb.discard(mb)  # a measurement that certainly writes its bit
            nq.update(qs)
            nb.update(cond)
    keep.reverse()
    return keep


def compact_all_qubits(c, term: Set[int] = None, members: bool = False):
    """The QDG slice of every qubit in one backward pass. Each location carries the set of criterion qubits whose
    slice needs it (an integer used as a bit set). Operation k is in the slice of exactly the criteria in S, the union
    of the sets on the locations it writes. It then adds S to the qubits it acts on and the bits its condition reads,
    and a measurement that certainly writes its bit clears that bit's set. This is n runs of compact_slice at once.
    Returns the total number of (criterion, operation) memberships, and with members=True the slice of each qubit."""
    term = compact_terminal(c) if term is None else term
    rq = [1 << q for q in range(c.n_qubits)]
    rb = [0] * c.n_bits
    total = 0
    sl = [[] for _ in range(c.n_qubits)] if members else None
    qoff, qsa, kind, mbit, coff, csa = c.qoff, c.qs, c.kind, c.mbit, c.coff, c.cs
    for k in range(len(c) - 1, -1, -1):
        if kind[k] == 3 or k in term:
            continue
        a, b = qoff[k], qoff[k + 1]
        s = 0
        for i in range(a, b):
            s |= rq[qsa[i]]
        mb = mbit[k]
        if mb >= 0:
            s |= rb[mb]
        if not s:
            continue
        total += s.bit_count()
        if members:
            t = s
            while t:
                low = t & -t
                sl[low.bit_length() - 1].append(k)
                t ^= low
        ca, cb = coff[k], coff[k + 1]
        if mb >= 0 and ca == cb:
            rb[mb] &= ~s
        for i in range(a, b):
            rq[qsa[i]] |= s
        for i in range(ca, cb):
            rb[csa[i]] |= s
    if members:
        for x in sl:
            x.reverse()
    return total, sl


def compact_from_circuit(circ: Circuit):
    """The compact form of an Op trace whose operations are all resolved (one qubit per argument, at most one bit per
    measurement, no may-operation). Raises ValueError otherwise; such traces stay on wire_slice."""
    from tool.qasm import Compact  # noqa: PLC0415
    c = Compact(circ.n("q"), circ.n("c"))
    names = {}
    for op in circ.ops:
        if op.may or any(len(s) != 1 for s in op.qubits) or any(len(s) != 1 for s in op.clbits) or len(op.clbits) > 1:
            raise ValueError("trace has over-approximated operations")
        c.kind.append(1 if op.name == "measure" else 2 if op.name == "reset" else 3 if op.name in NOT_SLICED else 0)
        c.qs.extend(next(iter(s)) for s in op.qubits)
        c.qoff.append(len(c.qs))
        c.mbit.append(next(iter(op.clbits[0])) if op.name == "measure" and op.clbits else -1)
        c.cs.extend(sorted(op.cond))
        c.coff.append(len(c.cs))
        c.line.append(op.line)
        c.name_of.append(names.setdefault(op.name, len(names)))
    c.names = list(names)
    return c
