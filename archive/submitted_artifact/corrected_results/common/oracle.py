"""Exact semantic oracle for circuits with mid-circuit measurement, reset and classical feedback.

The circuit is simulated exactly as an ensemble of pure-state branches. Every mid-circuit measurement
or reset splits each branch by outcome, with the outcome's exact probability and the classical bits
updated, and `if_else` blocks are resolved per branch. The result is the exact reduced density matrix
(2x2) of each requested qubit at the end of the circuit, averaged over all branches.

A measurement is *terminal* when no later instruction acts on its qubit and its classical bit is
never read by a later condition. A terminal measurement cannot change any other qubit's reduced state
(no-signalling), and it dephases its own qubit in the Z basis. It is applied that way, without
branching, which keeps the branch count small for circuits that end by measuring every qubit.

No sampling and no fallback: an unsupported instruction or more than MAX_BRANCHES branches raises
OracleError, and the caller records the circuit as not evaluable.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Clbit, ClassicalRegister
from qiskit.quantum_info import Operator

MAX_BRANCHES = 4096
PROB_FLOOR = 1e-14
SKIP = {"barrier", "delay"}


class OracleError(RuntimeError):
    pass


def _apply(psi: np.ndarray, mat: np.ndarray, axes: Sequence[int]) -> np.ndarray:
    """Apply a k-qubit matrix (qiskit little-endian over `axes` = tensor axes of qargs[0..k-1])."""
    k = len(axes)
    m = mat.reshape((2,) * (2 * k))
    # In the reshaped matrix the output axes are ordered (q_{k-1}, ..., q_0), then the same for inputs.
    in_axes = list(range(k, 2 * k))
    psi_axes = [axes[k - 1 - j] for j in range(k)]
    out = np.tensordot(m, psi, axes=(in_axes, psi_axes))
    return np.moveaxis(out, list(range(k)), psi_axes)


class _Sim:
    def __init__(self, qc: QuantumCircuit):
        self.qc = qc
        self.n = qc.num_qubits
        self.qidx = {q: i for i, q in enumerate(qc.qubits)}
        self.cidx = {c: i for i, c in enumerate(qc.clbits)}
        self.dephased: set[int] = set()
        # Keyed by (name, arity, params): within one circuit a gate name has a single definition.
        # (Not by id(op): qiskit creates operation objects lazily, so ids are reused.)
        self._mat_cache: Dict[tuple, np.ndarray] = {}

    def axis(self, q: int) -> int:
        return self.n - 1 - q  # tensor axis of qubit q (psi reshaped to (2,)*n, big-endian axes)

    def matrix(self, op) -> np.ndarray:
        key = (op.name, op.num_qubits, tuple(repr(p) for p in op.params))
        if key not in self._mat_cache:
            try:
                self._mat_cache[key] = np.asarray(op.to_matrix(), dtype=complex)
            except Exception:
                try:
                    self._mat_cache[key] = Operator(op).data
                except Exception as exc:
                    raise OracleError(f"no matrix for instruction {op.name}: {exc}") from exc
        return self._mat_cache[key]

    # -- branch operations -------------------------------------------------------------------------
    def project(self, branches, q: int, clbit: int | None, then_reset: bool):
        out = []
        ax = self.axis(q)
        for p, psi, bits in branches:
            for b in (0, 1):
                part = np.take(psi, b, axis=ax)
                pb = float(np.vdot(part, part).real)
                if p * pb <= PROB_FLOOR:
                    continue
                new = np.zeros_like(psi)
                target = 0 if then_reset else b
                idx = [slice(None)] * self.n
                idx[ax] = target
                new[tuple(idx)] = part / np.sqrt(pb)
                nb = bits if clbit is None else bits[:clbit] + (b,) + bits[clbit + 1:]
                out.append((p * pb, new, nb))
        if len(out) > MAX_BRANCHES:
            raise OracleError(f"more than {MAX_BRANCHES} measurement branches")
        return out

    @staticmethod
    def _cond_value(cond, bits, cmap) -> bool:
        target, value = cond
        if isinstance(target, Clbit):
            return bits[cmap[target]] == int(value)
        if isinstance(target, ClassicalRegister):
            v = sum(bits[cmap[c]] << i for i, c in enumerate(target))
            return v == int(value)
        raise OracleError(f"unsupported condition {cond!r}")

    def run_block(self, data, branches, qmap, cmap, terminal: set[int] | None = None):
        for k, inst in enumerate(data):
            op = inst.operation
            name = op.name
            qs = [qmap[q] for q in inst.qubits]
            if name in SKIP:
                continue
            if name == "measure":
                if terminal is not None and k in terminal:
                    self.dephased.add(qs[0])
                    continue
                branches = self.project(branches, qs[0], cmap[inst.clbits[0]], then_reset=False)
            elif name == "reset":
                branches = self.project(branches, qs[0], None, then_reset=True)
            elif name == "if_else":
                cond = getattr(op, "condition", None)
                if cond is None or not isinstance(cond, tuple):
                    raise OracleError("if_else without a (bit/register, value) condition")
                true_body, false_body = op.blocks[0], (op.blocks[1] if len(op.blocks) > 1 else None)
                taken, other = [], []
                for br in branches:
                    (taken if self._cond_value(cond, br[2], cmap) else other).append(br)
                for body, group in ((true_body, taken), (false_body, other)):
                    if body is None or not group:
                        continue
                    bq = {bqb: qmap[oq] for bqb, oq in zip(body.qubits, inst.qubits)}
                    bc = dict(cmap)
                    bc.update({bcb: cmap[oc] for bcb, oc in zip(body.clbits, inst.clbits)})
                    group[:] = self.run_block(body.data, group, bq, bc)
                branches = taken + other
            elif op.num_clbits == 0 and getattr(op, "blocks", None) is None:
                mat = self.matrix(op)
                axes = [self.axis(q) for q in qs]
                branches = [(p, _apply(psi, mat, axes), bits) for p, psi, bits in branches]
            else:
                raise OracleError(f"unsupported instruction {name}")
        return branches


def terminal_measurements(qc: QuantumCircuit) -> set[int]:
    """Indices of measurements that no later instruction depends on (see module docstring)."""
    data = qc.data
    read_later: set = set()
    touched_later: set = set()
    out = set()
    for k in range(len(data) - 1, -1, -1):
        inst = data[k]
        name = inst.operation.name
        if name == "measure" and inst.qubits[0] not in touched_later and inst.clbits[0] not in read_later:
            out.add(k)
        if name == "if_else":
            cond = inst.operation.condition
            tgt = cond[0]
            read_later.update([tgt] if isinstance(tgt, Clbit) else list(tgt))
        if name not in SKIP:
            touched_later.update(inst.qubits)
    return out


def reduced_states(qc: QuantumCircuit, qubits: Iterable[int]) -> Dict[int, np.ndarray]:
    """Exact end-of-circuit 2x2 reduced density matrix of each qubit in `qubits`."""
    sim = _Sim(qc)
    if sim.n > 16:
        raise OracleError("more than 16 qubits")
    psi = np.zeros((2,) * sim.n, dtype=complex)
    psi[(0,) * sim.n] = 1.0
    branches = [(1.0, psi, (0,) * qc.num_clbits)]
    branches = sim.run_block(qc.data, branches, sim.qidx, sim.cidx, terminal_measurements(qc))
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


def fidelity(rho: np.ndarray, sigma: np.ndarray) -> float:
    """Uhlmann fidelity of two single-qubit density matrices (exact closed form for 2x2)."""
    f = np.trace(rho @ sigma).real + 2.0 * np.sqrt(max(np.linalg.det(rho).real, 0.0) * max(np.linalg.det(sigma).real, 0.0))
    return float(min(max(f, 0.0), 1.0))


def trace_distance(rho: np.ndarray, sigma: np.ndarray) -> float:
    return float(0.5 * np.abs(np.linalg.eigvalsh(rho - sigma)).sum())
