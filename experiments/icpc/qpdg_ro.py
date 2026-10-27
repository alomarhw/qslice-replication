"""S-yzro and S-yzrof: the QPDG under the read-only-control reading (Deviation I-19, exploratory; review item 3).

S-yz (slicers/yuzhao.py) reads Yu & Zhao's data dependence as "every gate writes every qubit it acts on" (D-yz-3).
The other reading of a prose-only definition is the classical one, in which a controlled gate reads its controls
and writes only its targets. These slicers keep every other choice of the S-yz design log and change only D-yz-3:
  data     the rule of S-cpdg (icpc/cpdg.py): a controlled gate reads all its qubits and writes its targets, any
           other instruction reads and writes all its qubits, a measurement also writes its bit, a condition reads
           the bits it tests; u depends on the latest earlier writer of every location it reads;
  entangl. S-yzro: the static closure of S-yz (D-yz-5): qubits connected by a two-qubit gate anywhere are one
           component, and v -> u (v < u) when a qubit of v and a different qubit of u share a component;
           S-yzrof: the flow-sensitive closure of S-yzf (component taken just after u);
  seed     the last instruction acting on the criterion qubit, controls included (D-yz-2).
The slice is backward reachability from the seed. Both were fixed before they were run on any circuit.
"""

from __future__ import annotations

from typing import List, Set

from qiskit import QuantumCircuit

from icpc.cpdg import _condition_bits


def _rw(qc: QuantumCircuit):
    reads, writes, qubits = [], [], []
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
        qubits.append(qs)
    return reads, writes, qubits


def _preds(qc: QuantumCircuit, flow: bool) -> List[Set[int]]:
    reads, writes, qubits = _rw(qc)
    preds: List[Set[int]] = [set() for _ in qc.data]
    last = {}
    for u in range(len(qc.data)):
        for x in reads[u]:
            if x in last:
                preds[u].add(last[x])
        for x in writes[u]:
            last[x] = u
    parent = list(range(qc.num_qubits))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    if not flow:
        for qs in qubits:
            if len(qs) == 2:
                parent[find(qs[0])] = find(qs[1])
    for u, qs in enumerate(qubits):
        if flow and len(qs) == 2:
            parent[find(qs[0])] = find(qs[1])
        for v in range(u):
            if any(a != b and find(a) == find(b) for a in qubits[v] for b in qs):
                preds[u].add(v)
    return preds


def yzro_slice(qc: QuantumCircuit, t: int, flow: bool = False) -> Set[int]:
    on_t = [k for k, inst in enumerate(qc.data) if t in {qc.find_bit(q).index for q in inst.qubits}]
    if not on_t:
        return set()
    preds = _preds(qc, flow)
    seen, stack = set(), [max(on_t)]
    while stack:
        x = stack.pop()
        if x not in seen:
            seen.add(x)
            stack.extend(preds[x])
    return seen
