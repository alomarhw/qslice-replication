"""Oracle extensions for the ICPC experiments (PROTOCOL_ICPC.md sections 2.1, 3.2, 3.4, 3.5).

Built on common/oracle.py, unchanged: the same exact pure-state branching simulator, imported as is.
Nothing here imports slicer code. Added:
  - product input states, prepended as single-qubit unitaries (section 3.2);
  - joint reduced states rho_W of a qubit set W, with terminal-measurement dephasing (section 3.4);
  - an optional higher qubit limit for corpus L (section 3.5);
  - the two perturbations of the semantic-dependence ground truth (section 2.1, Deviation I-1):
    a joint unitary inserted right after an instruction, and the inversion of a measurement's
    recorded outcome for the conditions that read it before the bit is next written.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Clbit, ClassicalRegister, IfElseOp
from qiskit.circuit.library import UnitaryGate
from scipy.stats import unitary_group

from common import oracle as base
from common.oracle import OracleError, fidelity, trace_distance  # noqa: F401  (re-exported)

FIDELITY_EPS = 1e-6


# ----------------------------------------------------------------------------------------------
# Random objects
# ----------------------------------------------------------------------------------------------
def haar_unitary(dim: int, rng: np.random.Generator) -> np.ndarray:
    return unitary_group.rvs(dim, random_state=rng)


def haar_product_input(n: int, rng: np.random.Generator) -> List[np.ndarray]:
    """One Haar-random single-qubit unitary per qubit; applied to |0>, a Haar-random product state."""
    return [haar_unitary(2, rng) for _ in range(n)]


def basis_input(n: int, rng: np.random.Generator) -> List[np.ndarray]:
    """A uniformly random computational-basis input, as X / identity per qubit."""
    x, i = np.array([[0, 1], [1, 0]], complex), np.eye(2, dtype=complex)
    return [x if b else i for b in rng.integers(0, 2, size=n)]


# ----------------------------------------------------------------------------------------------
# Circuit transformations
# ----------------------------------------------------------------------------------------------
def with_input(qc: QuantumCircuit, prep: Optional[Sequence[np.ndarray]]) -> QuantumCircuit:
    """`qc` preceded by one single-qubit unitary per qubit (None = the |0...0> input)."""
    if prep is None:
        return qc
    out = qc.copy_empty_like()
    for q, u in enumerate(prep):
        out.append(UnitaryGate(u, check_input=False), [out.qubits[q]])
    for inst in qc.data:
        out.append(inst)
    return out


def insert_unitary_after(qc: QuantumCircuit, k: int, u: np.ndarray) -> QuantumCircuit:
    """`qc` with the unitary `u` on instruction k's qubits inserted right after instruction k."""
    inst_k = qc.data[k]
    out = qc.copy_empty_like()
    for j, inst in enumerate(qc.data):
        out.append(inst)
        if j == k:
            out.append(UnitaryGate(u, check_input=False), list(inst_k.qubits))
    return out


def _flip_condition(cond, bit: Clbit):
    target, value = cond
    if isinstance(target, Clbit):
        return (target, 1 - int(value)) if target == bit else cond
    if isinstance(target, ClassicalRegister) and bit in list(target):
        return (target, int(value) ^ (1 << list(target).index(bit)))
    return cond


def flip_measurement_outcome(qc: QuantumCircuit, k: int) -> Optional[QuantumCircuit]:
    """`qc` in which the outcome recorded by measurement k is inverted for every later condition
    that reads it, up to the next instruction that writes the same bit. None if nothing reads it."""
    meas = qc.data[k]
    bit = meas.clbits[0]
    out = qc.copy_empty_like()
    changed, live = False, True
    for j, inst in enumerate(qc.data):
        op = inst.operation
        if j > k and live and isinstance(op, IfElseOp):
            new_cond = _flip_condition(op.condition, bit)
            if new_cond != op.condition:
                op = IfElseOp(new_cond, op.blocks[0], op.blocks[1] if len(op.blocks) > 1 else None, op.label)
                changed = True
        if j > k and op.name == "measure" and bit in inst.clbits:
            live = False
        out.append(op, inst.qubits, inst.clbits)
    return out if changed else None


def delete_instruction(qc: QuantumCircuit, k: int) -> QuantumCircuit:
    out = qc.copy_empty_like()
    for j, inst in enumerate(qc.data):
        if j != k:
            out.append(inst)
    return out


# ----------------------------------------------------------------------------------------------
# Reduced states
# ----------------------------------------------------------------------------------------------
class _Sim(base._Sim):
    """The base simulator, with inserted unitaries cached by their exact matrix bytes. The base cache
    keys by repr(params), which numpy abbreviates for matrices of more than 1,000 entries, so two
    different random unitaries on 5 or more qubits could otherwise share a cache entry."""

    def matrix(self, op) -> np.ndarray:
        if op.name == "unitary" and op.params:  # a QASM-defined gate that is merely named "unitary" has no matrix parameter
            m = np.asarray(op.params[0], dtype=complex)
            key = ("unitary", m.shape, m.tobytes())
            if key not in self._mat_cache:
                self._mat_cache[key] = m
            return self._mat_cache[key]
        return super().matrix(op)


def _branches(qc: QuantumCircuit, max_qubits: int):
    sim = _Sim(qc)
    if sim.n > max_qubits:
        raise OracleError(f"more than {max_qubits} qubits")
    if sim.n > 16:
        base.MAX_BRANCHES = 64  # PROTOCOL_ICPC.md 3.5: branch limit above 16 qubits (memory)
    try:
        psi = np.zeros((2,) * sim.n, dtype=complex)
        psi[(0,) * sim.n] = 1.0
        branches = [(1.0, psi, (0,) * qc.num_clbits)]
        branches = sim.run_block(qc.data, branches, sim.qidx, sim.cidx, base.terminal_measurements(qc))
    finally:
        base.MAX_BRANCHES = 4096
    return sim, branches


def reduced_states(qc: QuantumCircuit, qubits: Iterable[int], max_qubits: int = 16) -> Dict[int, np.ndarray]:
    """Exact 2x2 reduced states, computed as common.oracle.reduced_states does (up to `max_qubits`)."""
    sim, branches = _branches(qc, max_qubits)
    out = {}
    for q in qubits:
        ax = sim.axis(q)
        rho = np.zeros((2, 2), dtype=complex)
        for p, psi, _ in branches:
            m = np.moveaxis(psi, ax, 0).reshape(2, -1)
            rho += p * (m @ m.conj().T)
        rho /= sum(p for p, _, _ in branches)
        if q in sim.dephased:
            rho = np.diag(np.diag(rho))
        out[q] = rho
    return out


def joint_reduced_state(qc: QuantumCircuit, W: Sequence[int], max_qubits: int = 16) -> np.ndarray:
    """Exact reduced state of the qubit set W (ordered as given; W[0] is the least significant)."""
    sim, branches = _branches(qc, max_qubits)
    W = list(W)
    axes = [sim.axis(q) for q in reversed(W)]  # most significant first in the matrix index
    dim = 2 ** len(W)
    rho = np.zeros((dim, dim), dtype=complex)
    for p, psi, _ in branches:
        m = np.moveaxis(psi, axes, list(range(len(W)))).reshape(dim, -1)
        rho += p * (m @ m.conj().T)
    rho /= sum(p for p, _, _ in branches)
    for i, q in enumerate(W):  # a terminal measurement dephases its own qubit
        if q in sim.dephased:
            mask = np.array([((r >> i) & 1) == ((c >> i) & 1) for r in range(dim) for c in range(dim)]).reshape(dim, dim)
            rho = np.where(mask, rho, 0)
    return rho


def uhlmann_fidelity(rho: np.ndarray, sigma: np.ndarray) -> float:
    """Uhlmann fidelity (squared convention) for density matrices of any size."""
    if rho.shape == (2, 2):
        return fidelity(rho, sigma)
    w, v = np.linalg.eigh((rho + rho.conj().T) / 2)
    sq = (v * np.sqrt(np.clip(w, 0, None))) @ v.conj().T
    m = sq @ sigma @ sq
    ev = np.clip(np.linalg.eigvalsh((m + m.conj().T) / 2), 0, None)
    return float(min(max(np.sum(np.sqrt(ev)) ** 2, 0.0), 1.0))
