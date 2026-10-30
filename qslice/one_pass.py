"""The QDG slice of Section IV-B by one backward pass over the circuit, without building a graph (Deviation I-28).

Walk the circuit from its end with a needed set that starts at the criterion qubit. An operation whose locations meet
the needed set joins the slice, and its locations join the needed set.

bits="graph"  Definition 4 as the paper states it, and as the study's graph computes it (slicer `lc`): a conditioned operation depends on the
              most recent earlier measurement of each bit its condition reads, and a measurement reads no bit.
bits="def4"   the earlier wording of Definition 4, kept for the check of Deviation I-28: every location of an
              operation, its qubits, its measured bits and its condition's bits, is read and written.
"""

from __future__ import annotations

from typing import Set

from qiskit import QuantumCircuit
from qiskit.circuit import Clbit


def _locations(inst, qidx, cidx):
    op = inst.operation
    qubits = {qidx[q] for q in inst.qubits if q in qidx}
    measured = {cidx[b] for b in inst.clbits if b in cidx} if op.name == "measure" else set()
    cond = set()
    c = getattr(op, "condition", None)
    if c is not None:
        bits = [c[0]] if isinstance(c[0], Clbit) else list(c[0])
        cond = {cidx[b] for b in bits if b in cidx}
    return qubits, measured, cond


def qdg_slice(qc: QuantumCircuit, target: int, bits: str = "graph") -> Set[int]:
    """Positions of the operations in the QDG slice of qubit `target`."""
    qidx = {q: i for i, q in enumerate(qc.qubits)}
    cidx = {b: i for i, b in enumerate(qc.clbits)}
    need_q, need_c, keep = {target}, set(), set()
    for pos in range(len(qc.data) - 1, -1, -1):
        qubits, measured, cond = _locations(qc.data[pos], qidx, cidx)
        if bits == "def4":
            cbits = measured | cond
            if qubits & need_q or cbits & need_c:
                keep.add(pos)
                need_q |= qubits
                need_c |= cbits
        else:
            hit_c = measured & need_c
            if qubits & need_q or hit_c:
                keep.add(pos)
                need_q |= qubits
                need_c -= measured  # the most recent earlier measurement of a bit is the one a condition reads
                need_c |= cond
    return keep


def qdg_forward(qc: QuantumCircuit, k: int) -> Set[int]:
    """Positions of the operations in the forward slice of operation k (Definition 4, bits as the graph treats them)."""
    qidx = {q: i for i, q in enumerate(qc.qubits)}
    cidx = {b: i for i, b in enumerate(qc.clbits)}
    q0, m0, _ = _locations(qc.data[k], qidx, cidx)
    reach_q, reach_c, keep = set(q0), set(m0), {k}
    for pos in range(k + 1, len(qc.data)):
        qubits, measured, cond = _locations(qc.data[pos], qidx, cidx)
        if qubits & reach_q or cond & reach_c:
            keep.add(pos)
            reach_q |= qubits
            reach_c |= measured
        else:
            reach_c -= measured  # an unreached measurement overwrites the bit
    return keep
