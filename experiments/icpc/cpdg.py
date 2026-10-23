"""S-cpdg: the full classical program dependence graph slice, data plus control dependence (Deviation I-12).

S-du (slicers/registry.py -> qslice/qdg.py::naive_classical_backward_slice) ports classical data
dependence only: a controlled gate reads its controls and targets and writes its targets, any other
instruction reads and writes all its qubits, and classical bits are ignored. A classical slicer also
follows control dependence. S-cpdg keeps S-du's qubit rule unchanged and adds the classical bits:
  - a measurement also writes its classical bit;
  - an if_else also reads the bits its condition tests (control dependence on the measurement that
    wrote them).
The backward pass is S-du's, with reaching definitions: an instruction joins the slice when it writes a needed
location, its classical writes stop being needed, and the locations it reads become needed. On a circuit without classical bits S-cpdg equals S-du; the run checks
this on every unitary pair. What S-cpdg still lacks is quantum dependence, the effect of a controlled
gate on its controls.
"""

from __future__ import annotations

from typing import Set

from qiskit import ClassicalRegister, QuantumCircuit


def _condition_bits(op, qc: QuantumCircuit) -> Set[int]:
    cond = getattr(op, "condition", None)
    if not cond:
        return set()
    tgt = cond[0]
    bits = list(tgt) if isinstance(tgt, ClassicalRegister) else [tgt]
    return {("c", qc.find_bit(b).index) for b in bits}


def cpdg_slice(qc: QuantumCircuit, target_qubit: int) -> Set[int]:
    reads, writes = [], []
    for inst in qc.data:
        op = inst.operation
        qs = [qc.find_bit(q).index for q in inst.qubits]
        nc = int(getattr(op, "num_ctrl_qubits", 0) or 0)
        if nc and len(qs) > nc:
            r, w = {("q", x) for x in qs}, {("q", x) for x in qs[nc:]}
        else:
            r = w = {("q", x) for x in qs}
        r, w = set(r), set(w)
        if op.name == "measure":
            w |= {("c", qc.find_bit(c).index) for c in inst.clbits}
        if op.name == "if_else":
            r |= _condition_bits(op, qc)
        reads.append(r)
        writes.append(w)
    # Reaching definitions: a write kills the location. For qubits this changes nothing (every rule reads what it
    # writes); for a classical bit it stops at the most recent measurement, as the wire rule's control edges do.
    needed, include = {("q", target_qubit)}, set()
    for i in range(len(qc.data) - 1, -1, -1):
        if writes[i] & needed:
            include.add(i)
            needed = (needed - {x for x in writes[i] if x[0] == "c"}) | reads[i]
    return include
