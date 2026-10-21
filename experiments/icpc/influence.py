"""Semantic-dependence ground truth and as-written contribution (PROTOCOL_ICPC.md section 2.1, Deviation I-1).

influence(qc): for every instruction k, the qubits q it influences. k influences q iff, for some input
among |0...0> and 10 Haar-random product inputs, one of
  - 2 Haar-random unitaries on the joint space of k's qubits, inserted right after k, or
  - for a measurement, the inversion of its recorded outcome for the conditions that read it,
changes q's exact unconditional end-of-circuit reduced state (Uhlmann fidelity < 1 - 1e-6).

contribution(qc): for every instruction k, the qubits whose reduced state changes when k alone is
deleted, at |0...0> and at the same 10 product inputs (reported per input class).

Computed by the oracle only (icpc/oracle_icpc.py); no slicer code is imported.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set

import numpy as np
from qiskit import QuantumCircuit

from icpc import oracle_icpc as oi

N_INPUTS, N_PERTURBATIONS, SEED = 10, 2, 20261023
SKIP = {"barrier", "delay"}


def _inputs(n: int, seed: int = SEED) -> List[Optional[Sequence[np.ndarray]]]:
    rng = np.random.default_rng(seed)
    return [None] + [oi.haar_product_input(n, rng) for _ in range(N_INPUTS)]


def _changed(base: Dict[int, np.ndarray], other: Dict[int, np.ndarray]) -> Set[int]:
    return {q for q in base if oi.uhlmann_fidelity(base[q], other[q]) < 1 - oi.FIDELITY_EPS}


def influence(qc: QuantumCircuit, max_qubits: int = 16, seed: int = SEED) -> Dict[int, Set[int]]:
    """{instruction position: set of influenced qubits}."""
    n = qc.num_qubits
    qs = range(n)
    inputs = _inputs(n, seed)
    rng = np.random.default_rng(seed + 1)
    perturb = {}  # same perturbation unitaries for every input
    for k, inst in enumerate(qc.data):
        if inst.operation.name in SKIP:
            continue
        dim = 2 ** len(inst.qubits)
        perturb[k] = [oi.haar_unitary(dim, rng) for _ in range(N_PERTURBATIONS)]
    flips = {k: oi.flip_measurement_outcome(qc, k) for k, inst in enumerate(qc.data)
             if inst.operation.name == "measure"}
    out: Dict[int, Set[int]] = {k: set() for k in perturb}
    for prep in inputs:
        base = oi.reduced_states(oi.with_input(qc, prep), qs, max_qubits)
        for k in perturb:
            if len(out[k]) == n:
                continue
            for u in perturb[k]:
                pert = oi.reduced_states(oi.with_input(oi.insert_unitary_after(qc, k, u), prep), qs, max_qubits)
                out[k] |= _changed(base, pert)
            if flips.get(k) is not None:
                pert = oi.reduced_states(oi.with_input(flips[k], prep), qs, max_qubits)
                out[k] |= _changed(base, pert)
    return out


def contribution(qc: QuantumCircuit, max_qubits: int = 16, seed: int = SEED) -> Dict[int, Dict[str, Set[int]]]:
    """{position: {"zero": qubits changed by deleting it at |0...0>, "any": at some tested input}}."""
    n = qc.num_qubits
    qs = range(n)
    inputs = _inputs(n, seed)
    out = {k: {"zero": set(), "any": set()} for k, inst in enumerate(qc.data) if inst.operation.name not in SKIP}
    for i, prep in enumerate(inputs):
        base = oi.reduced_states(oi.with_input(qc, prep), qs, max_qubits)
        for k in out:
            ch = _changed(base, oi.reduced_states(oi.with_input(oi.delete_instruction(qc, k), prep), qs, max_qubits))
            out[k]["any"] |= ch
            if i == 0:
                out[k]["zero"] |= ch
    return out


def influence_sets(inf: Dict[int, Set[int]], n_qubits: int) -> Dict[int, Set[int]]:
    """Invert to {qubit: positions that influence it}."""
    by_q: Dict[int, Set[int]] = {q: set() for q in range(n_qubits)}
    for k, qubits in inf.items():
        for q in qubits:
            by_q[q].add(k)
    return by_q
