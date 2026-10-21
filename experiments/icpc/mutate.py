"""Seeded faults for RQ3 (PROTOCOL_ICPC.md section 4.1): ten operators, each cited to its source.

| Id     | Operator                                             | Provenance                              |
|--------|------------------------------------------------------|-----------------------------------------|
| M-ins  | insert a random 1-qubit gate from {x,y,z,h,s,t,sx}    | Muskit; QMutPy                          |
| M-del  | delete a gate                                        | Muskit; QMutPy                          |
| M-rep  | replace a gate, same arity (1q set above; 2q {cx,cz,cy,swap}) | Muskit; QMutPy                 |
| M-mins | insert a mid-circuit measurement into a fresh bit    | QMutPy                                  |
| M-mdel | delete a non-terminal measurement                    | QMutPy                                  |
| M-cts  | swap a control and a target of a controlled gate     | QuMu "Swap controls and controlled qubits" |
| M-crm  | remove one control of a controlled gate              | QuMu "Control gate removal"             |
| M-qsw  | re-target one operand of a multi-qubit gate          | QuMu bridging fault                     |
| M-ent  | force unentanglement / entanglement corruption on an H feeding an entangling gate | QuMu entanglement faults |
| M-par  | perturb one angle by delta ~ U[pi/8, pi]             | ours                                    |

Sampling: up to 5 mutants per operator and circuit, uniformly over the operator's valid sites, seed
20261022 (per circuit, derived from the circuit path). Every mutant carries its fault site as
instruction positions in the MUTANT circuit: the changed or inserted instruction, or, for a deletion,
the instructions immediately before and after the deletion point on the deleted gate's qubits.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Set, Tuple

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit
from qiskit.circuit import library as lib

SEED, PER_OPERATOR = 20261022, 5
ONE_Q = ["x", "y", "z", "h", "s", "t", "sx"]
TWO_Q = ["cx", "cz", "cy", "swap"]
NON_GATES = {"measure", "reset", "barrier", "delay", "if_else"}
OPERATORS = ["M-ins", "M-del", "M-rep", "M-mins", "M-mdel", "M-cts", "M-crm", "M-qsw", "M-ent", "M-par"]
PROVENANCE = {"M-ins": "Muskit; QMutPy", "M-del": "Muskit; QMutPy", "M-rep": "Muskit; QMutPy",
              "M-mins": "QMutPy", "M-mdel": "QMutPy", "M-cts": "QuMu", "M-crm": "QuMu", "M-qsw": "QuMu",
              "M-ent": "QuMu", "M-par": "ours"}


@dataclass
class Mutant:
    operator: str
    site: str
    circuit: QuantumCircuit
    fault_site: Set[int] = field(default_factory=set)


def _gate(name: str):
    return {"x": lib.XGate, "y": lib.YGate, "z": lib.ZGate, "h": lib.HGate, "s": lib.SGate, "t": lib.TGate,
            "sx": lib.SXGate, "cx": lib.CXGate, "cz": lib.CZGate, "cy": lib.CYGate, "swap": lib.SwapGate}[name]()


def _rng(path: str, op: str) -> np.random.Generator:
    return np.random.default_rng(int(hashlib.sha256(f"{SEED}:{path}:{op}".encode()).hexdigest()[:12], 16))


def _rebuild(qc: QuantumCircuit, edits) -> QuantumCircuit:
    """edits: {position: list of (op, qubits, clbits) replacing it}; 'insert_before' keyed (pos, 'ins')."""
    out = qc.copy_empty_like()
    for extra in edits.get(("reg",), []):
        out.add_register(extra)
    for k, inst in enumerate(qc.data):
        for item in edits.get((k, "ins"), []):
            out.append(*item)
        for item in edits.get(k, [(inst.operation, inst.qubits, inst.clbits)]):
            out.append(*item)
    for item in edits.get((len(qc.data), "ins"), []):
        out.append(*item)
    return out


def _qidx(qc, inst):
    return [qc.find_bit(b).index for b in inst.qubits]


def _neighbours(qc: QuantumCircuit, k: int, qubits: Sequence[int]) -> Set[int]:
    """Positions, in the circuit with instruction k deleted, of the instructions immediately before and
    after the deletion point on `qubits`."""
    out = set()
    on = lambda j: bool(set(_qidx(qc, qc.data[j])) & set(qubits))  # noqa: E731
    before = [j for j in range(k) if on(j)]
    after = [j for j in range(k + 1, len(qc.data)) if on(j)]
    if before:
        out.add(before[-1])
    if after:
        out.add(after[0] - 1)
    return out


def _terminal_measurements(qc):
    from common.oracle import terminal_measurements
    return terminal_measurements(qc)


def sites(qc: QuantumCircuit, operator: str) -> List[Tuple]:
    data = qc.data
    n = qc.num_qubits
    gates = [k for k, i in enumerate(data) if i.operation.name not in NON_GATES]
    if operator == "M-ins":
        return [(k, q, g) for k in range(len(data) + 1) for q in range(n) for g in ONE_Q]
    if operator == "M-del":
        return [(k,) for k in gates]
    if operator == "M-rep":
        out = []
        for k in gates:
            op = data[k].operation
            pool = ONE_Q if op.num_qubits == 1 else TWO_Q if op.num_qubits == 2 else []
            out += [(k, g) for g in pool if g != op.name]
        return out
    if operator == "M-mins":
        return [(k, q) for k in range(len(data) + 1) for q in range(n)]
    if operator == "M-mdel":
        term = _terminal_measurements(qc)
        return [(k,) for k, i in enumerate(data) if i.operation.name == "measure" and k not in term]
    ctrl = [k for k in gates if int(getattr(data[k].operation, "num_ctrl_qubits", 0) or 0) >= 1
            and hasattr(data[k].operation, "base_gate")]
    if operator == "M-cts":
        return [(k,) for k in ctrl]
    if operator == "M-crm":
        return [(k,) for k in ctrl]
    if operator == "M-qsw":
        return [(k, slot, newq) for k in gates if data[k].operation.num_qubits >= 2
                for slot in range(data[k].operation.num_qubits)
                for newq in range(n) if newq not in _qidx(qc, data[k])]
    if operator == "M-ent":
        out = []
        for k in gates:
            if data[k].operation.name != "h":
                continue
            a = _qidx(qc, data[k])[0]
            nxt = next((j for j in range(k + 1, len(data)) if a in _qidx(qc, data[j])), None)
            if nxt is None:
                continue
            op = data[nxt].operation
            nc = int(getattr(op, "num_ctrl_qubits", 0) or 0)
            if op.num_qubits >= 2 and nc >= 1 and a in _qidx(qc, data[nxt])[:nc]:
                out += [(k, nxt, "unentangle"), (k, nxt, "corrupt")]
        return out
    if operator == "M-par":
        return [(k, p) for k in gates for p in range(len(data[k].operation.params))
                if isinstance(data[k].operation.params[p], (int, float))]
    raise ValueError(operator)


def apply(qc: QuantumCircuit, operator: str, site: Tuple, rng: np.random.Generator) -> Optional[Mutant]:
    data = qc.data
    if operator == "M-ins":
        k, q, g = site
        return Mutant(operator, f"insert {g} on q{q} before {k}",
                      _rebuild(qc, {(k, "ins"): [(_gate(g), [qc.qubits[q]], [])]}), {k})
    if operator in ("M-del", "M-mdel"):
        (k,) = site
        qs = _qidx(qc, data[k])
        return Mutant(operator, f"delete {data[k].operation.name} at {k}", _rebuild(qc, {k: []}), _neighbours(qc, k, qs))
    if operator == "M-rep":
        k, g = site
        inst = data[k]
        return Mutant(operator, f"replace {inst.operation.name} at {k} by {g}",
                      _rebuild(qc, {k: [(_gate(g), inst.qubits, [])]}), {k})
    if operator == "M-mins":
        k, q = site
        reg = ClassicalRegister(1, "mut")
        out = _rebuild(qc, {("reg",): [reg], (k, "ins"): [(lib.Measure(), [qc.qubits[q]], [reg[0]])]})
        return Mutant(operator, f"insert measure on q{q} before {k}", out, {k})
    if operator == "M-cts":
        (k,) = site
        inst = data[k]
        nc = inst.operation.num_ctrl_qubits
        qs = list(inst.qubits)
        qs[0], qs[nc] = qs[nc], qs[0]  # first control <-> first target
        return Mutant(operator, f"swap control/target of {inst.operation.name} at {k}",
                      _rebuild(qc, {k: [(inst.operation, qs, inst.clbits)]}), {k})
    if operator == "M-crm":
        (k,) = site
        inst = data[k]
        op = inst.operation
        nc = op.num_ctrl_qubits
        new = op.base_gate if nc == 1 else op.base_gate.control(nc - 1)
        return Mutant(operator, f"remove a control of {op.name} at {k}",
                      _rebuild(qc, {k: [(new, list(inst.qubits)[1:], [])]}), {k})
    if operator == "M-qsw":
        k, slot, newq = site
        inst = data[k]
        qs = list(inst.qubits)
        qs[slot] = qc.qubits[newq]
        return Mutant(operator, f"re-target operand {slot} of {inst.operation.name} at {k} to q{newq}",
                      _rebuild(qc, {k: [(inst.operation, qs, inst.clbits)]}), {k})
    if operator == "M-ent":
        k, nxt, how = site
        h = data[k]
        if how == "unentangle":
            return Mutant(operator, f"force unentanglement: delete h at {k} feeding {nxt}", _rebuild(qc, {k: []}),
                          _neighbours(qc, k, _qidx(qc, h)))
        cxi = data[nxt]
        out = _rebuild(qc, {k: [], nxt: [(cxi.operation, cxi.qubits, cxi.clbits), (h.operation, h.qubits, [])]})
        return Mutant(operator, f"entanglement corruption: move h at {k} after {nxt}", out, {nxt})  # moved H's new position
    if operator == "M-par":
        k, p = site
        inst = data[k]
        op = inst.operation.to_mutable()
        params = list(op.params)
        params[p] = float(params[p]) + float(rng.uniform(np.pi / 8, np.pi))
        op.params = params
        return Mutant(operator, f"perturb param {p} of {op.name} at {k}", _rebuild(qc, {k: [(op, inst.qubits, inst.clbits)]}), {k})
    raise ValueError(operator)


def mutants(qc: QuantumCircuit, path: str) -> List[Mutant]:
    out = []
    for operator in OPERATORS:
        rng = _rng(path, operator)
        ss = sites(qc, operator)
        if not ss:
            continue
        pick = rng.choice(len(ss), size=min(PER_OPERATOR, len(ss)), replace=False)
        for i in sorted(pick):
            try:
                m = apply(qc, operator, ss[i], rng)
            except Exception:  # an operator that does not apply to this gate type is skipped
                m = None
            if m is not None:
                out.append(m)
    return out
