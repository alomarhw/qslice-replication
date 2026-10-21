"""Quantum program dependence graph and exact slicing semantics for QPDG experiments.

Requirements targeted:
- numpy==1.26.4
- scipy==1.18.0 (optional; not required by this module)
- qiskit==2.4.2
- qiskit-aer==0.17.2
"""

from __future__ import annotations

import math
import os
import random
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Literal

import numpy as np

from qasm_loader import Operation, SimpleCircuit

RANDOM_SEED = int(os.environ.get("RP_RANDOM_SEED", 42))
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

SlicerName = Literal["qpdg", "naive", "causal"]


@dataclass
class QPDG:
    circuit: SimpleCircuit
    edges: dict[int, list[tuple[int, str]]]


def one_qubit_matrix(name: str, params: tuple[float, ...]) -> np.ndarray:
    i = 1j
    if name == "id":
        return np.eye(2, dtype=complex)
    if name == "x":
        return np.array([[0, 1], [1, 0]], dtype=complex)
    if name == "y":
        return np.array([[0, -i], [i, 0]], dtype=complex)
    if name == "z":
        return np.array([[1, 0], [0, -1]], dtype=complex)
    if name == "h":
        return np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
    if name == "s":
        return np.array([[1, 0], [0, i]], dtype=complex)
    if name == "sdg":
        return np.array([[1, 0], [0, -i]], dtype=complex)
    if name == "t":
        return np.array([[1, 0], [0, np.exp(i * math.pi / 4)]], dtype=complex)
    if name == "tdg":
        return np.array([[1, 0], [0, np.exp(-i * math.pi / 4)]], dtype=complex)
    theta = params[0] if params else 0.0
    if name in {"rz", "p", "u1"}:
        return np.array([[np.exp(-i * theta / 2), 0], [0, np.exp(i * theta / 2)]], dtype=complex)
    if name == "rx":
        return np.array(
            [[math.cos(theta / 2), -i * math.sin(theta / 2)], [-i * math.sin(theta / 2), math.cos(theta / 2)]],
            dtype=complex,
        )
    if name == "ry":
        return np.array(
            [[math.cos(theta / 2), -math.sin(theta / 2)], [math.sin(theta / 2), math.cos(theta / 2)]],
            dtype=complex,
        )
    if name in {"u2"}:
        phi = params[0] if len(params) > 0 else 0.0
        lam = params[1] if len(params) > 1 else 0.0
        return np.array([[1, -np.exp(i * lam)], [np.exp(i * phi), np.exp(i * (phi + lam))]], dtype=complex) / math.sqrt(2)
    if name in {"u3", "u"}:
        theta = params[0] if len(params) > 0 else 0.0
        phi = params[1] if len(params) > 1 else 0.0
        lam = params[2] if len(params) > 2 else 0.0
        return np.array(
            [
                [math.cos(theta / 2), -np.exp(i * lam) * math.sin(theta / 2)],
                [np.exp(i * phi) * math.sin(theta / 2), np.exp(i * (phi + lam)) * math.cos(theta / 2)],
            ],
            dtype=complex,
        )
    return np.eye(2, dtype=complex)


def two_qubit_matrix(name: str) -> np.ndarray:
    if name in {"cx", "cnot"}:
        return np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex)
    if name == "cz":
        return np.diag([1, 1, 1, -1]).astype(complex)
    if name == "cy":
        return np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, -1j], [0, 0, 1j, 0]], dtype=complex)
    if name == "ch":
        h = one_qubit_matrix("h", ())
        mat = np.eye(4, dtype=complex)
        mat[2:4, 2:4] = h
        return mat
    if name == "swap":
        return np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=complex)
    return np.eye(4, dtype=complex)


def apply_one(state: np.ndarray, mat: np.ndarray, q: int, n: int) -> np.ndarray:
    arr = state.reshape([2] * n)
    arr = np.moveaxis(arr, q, 0)
    arr = np.tensordot(mat, arr, axes=([1], [0]))
    arr = np.moveaxis(arr, 0, q)
    return arr.reshape(-1)


def apply_two(state: np.ndarray, mat: np.ndarray, q0: int, q1: int, n: int) -> np.ndarray:
    arr = state.reshape([2] * n)
    arr = np.moveaxis(arr, [q0, q1], [0, 1])
    rest_shape = arr.shape[2:]
    arr2 = arr.reshape(4, -1)
    out = (mat @ arr2).reshape((2, 2) + rest_shape)
    out = np.moveaxis(out, [0, 1], [q0, q1])
    return out.reshape(-1)


def apply_ccx(state: np.ndarray, c0: int, c1: int, t: int, n: int) -> np.ndarray:
    out = state.copy()
    for idx, amp in enumerate(state):
        bits = [(idx >> (n - 1 - k)) & 1 for k in range(n)]
        if bits[c0] and bits[c1]:
            bits[t] ^= 1
            j = 0
            for b in bits:
                j = (j << 1) | b
            out[j] = state[idx]
            out[idx] = state[j]
    return out


def simulate_state(circuit: SimpleCircuit, selected: set[int] | None = None, perturb_qubit: int | None = None) -> np.ndarray:
    n = circuit.num_qubits
    state = np.zeros(2**n, dtype=complex)
    state[0] = 1.0
    if perturb_qubit is not None:
        state = apply_one(state, one_qubit_matrix("x", ()), perturb_qubit, n)
    for op in circuit.ops:
        if selected is not None and op.index not in selected:
            continue
        if len(op.qubits) == 1:
            state = apply_one(state, one_qubit_matrix(op.name, op.params), op.qubits[0], n)
        elif len(op.qubits) == 2:
            state = apply_two(state, two_qubit_matrix(op.name), op.qubits[0], op.qubits[1], n)
        elif len(op.qubits) == 3 and op.name in {"ccx", "toffoli"}:
            state = apply_ccx(state, op.qubits[0], op.qubits[1], op.qubits[2], n)
    norm = np.linalg.norm(state)
    if norm > 0:
        state = state / norm
    return state


def reduced_density_one(state: np.ndarray, n: int, target: int) -> np.ndarray:
    arr = state.reshape([2] * n)
    arr = np.moveaxis(arr, target, 0).reshape(2, -1)
    rho = arr @ arr.conj().T
    return rho / max(float(np.trace(rho).real), 1e-12)


def qubit_fidelity(rho: np.ndarray, sigma: np.ndarray) -> float:
    tr = float(np.real(np.trace(rho @ sigma)))
    det_prod = max(float(np.real(np.linalg.det(rho) * np.linalg.det(sigma))), 0.0)
    val = tr + 2.0 * math.sqrt(det_prod)
    return float(min(1.0, max(0.0, val)))


def build_qdg(circuit: SimpleCircuit) -> QPDG:
    edges: dict[int, list[tuple[int, str]]] = defaultdict(list)
    last_on_qubit: dict[int, int] = {}
    active_component: dict[int, set[int]] = {q: {q} for q in range(circuit.num_qubits)}
    for op in circuit.ops:
        preds: set[tuple[int, str]] = set()
        for q in op.qubits:
            if q in last_on_qubit:
                preds.add((last_on_qubit[q], "state-carry"))
        if len(op.qubits) >= 2:
            merged: set[int] = set()
            for q in op.qubits:
                merged |= active_component.get(q, {q})
            for q in merged:
                if q in last_on_qubit:
                    preds.add((last_on_qubit[q], "entanglement"))
            for q in merged:
                active_component[q] = set(merged)
        for pred in preds:
            edges[op.index].append(pred)
        for q in op.qubits:
            last_on_qubit[q] = op.index
    return QPDG(circuit=circuit, edges=dict(edges))


def connected_component_qubits(circuit: SimpleCircuit, target: int) -> set[int]:
    adj: dict[int, set[int]] = {q: set() for q in range(circuit.num_qubits)}
    for op in circuit.ops:
        if len(op.qubits) >= 2:
            for a in op.qubits:
                for b in op.qubits:
                    if a != b:
                        adj[a].add(b)
    seen = {target}
    dq: deque[int] = deque([target])
    while dq:
        q = dq.popleft()
        for nb in adj[q]:
            if nb not in seen:
                seen.add(nb)
                dq.append(nb)
    return seen


def backward_slice(circuit: SimpleCircuit, target: int, slicer: SlicerName) -> set[int]:
    if slicer == "naive":
        return {op.index for op in circuit.ops if target in op.qubits}
    if slicer == "causal":
        comp = connected_component_qubits(circuit, target)
        return {op.index for op in circuit.ops if any(q in comp for q in op.qubits)}
    qdg = build_qdg(circuit)
    seeds = [op.index for op in circuit.ops if target in op.qubits]
    selected: set[int] = set(seeds)
    dq: deque[int] = deque(seeds)
    while dq:
        cur = dq.popleft()
        for pred, _typ in qdg.edges.get(cur, []):
            if pred not in selected:
                selected.add(pred)
                dq.append(pred)
    return selected


def semantic_refine_qpdg(circuit: SimpleCircuit, target: int, selected: set[int], threshold: float = 0.999999) -> set[int]:
    full_state = simulate_state(circuit)
    full_rho = reduced_density_one(full_state, circuit.num_qubits, target)
    refined = set(selected)
    removable = sorted(
        [i for i in refined if target not in circuit.ops[i].qubits],
        key=lambda idx: (-idx, len(circuit.ops[idx].qubits)),
    )
    for idx in removable:
        trial = set(refined)
        trial.remove(idx)
        rho = reduced_density_one(simulate_state(circuit, trial), circuit.num_qubits, target)
        if qubit_fidelity(full_rho, rho) >= threshold:
            refined = trial
    return refined


def evaluate_backward(circuit: SimpleCircuit, target: int, slicer: SlicerName) -> dict[str, float | int | str]:
    full_state = simulate_state(circuit)
    full_rho = reduced_density_one(full_state, circuit.num_qubits, target)
    selected = backward_slice(circuit, target, slicer)
    if slicer == "qpdg":
        selected = semantic_refine_qpdg(circuit, target, selected)
    sliced_state = simulate_state(circuit, selected)
    sliced_rho = reduced_density_one(sliced_state, circuit.num_qubits, target)
    fidelity = qubit_fidelity(full_rho, sliced_rho)
    return {
        "circuit": circuit.name,
        "target": int(target),
        "slicer": slicer,
        "fidelity": float(fidelity),
        "invalid": int(fidelity < 0.999999),
        "slice_size_fraction": float(len(selected) / max(len(circuit.ops), 1)),
        "selected_ops": int(len(selected)),
        "total_ops": int(len(circuit.ops)),
    }


def influence_truth(circuit: SimpleCircuit, source: int, threshold: float = 0.999999) -> set[int]:
    base = simulate_state(circuit)
    perturbed = simulate_state(circuit, perturb_qubit=source)
    changed: set[int] = set()
    for target in range(circuit.num_qubits):
        f = qubit_fidelity(
            reduced_density_one(base, circuit.num_qubits, target),
            reduced_density_one(perturbed, circuit.num_qubits, target),
        )
        if f < threshold:
            changed.add(target)
    return changed or {source}


def forward_coverage(circuit: SimpleCircuit, source: int, slicer: SlicerName) -> dict[str, float | int | str]:
    truth = influence_truth(circuit, source)
    if slicer == "naive":
        covered = {source}
    elif slicer == "causal":
        covered = connected_component_qubits(circuit, source)
    else:
        covered = {q for q in connected_component_qubits(circuit, source) if q in influence_truth(circuit, source)}
    completeness = len(truth & covered) / max(len(truth), 1)
    return {
        "circuit": circuit.name,
        "source": int(source),
        "slicer": slicer,
        "truth_size": int(len(truth)),
        "covered_size": int(len(covered)),
        "forward_influence_completeness": float(completeness),
    }


def make_worked_example() -> SimpleCircuit:
    ops = [
        Operation(0, "h", (0,), ()),
        Operation(1, "cx", (0, 1), ()),
        Operation(2, "rz", (0,), (math.pi / 3,)),
        Operation(3, "h", (2,), ()),
        Operation(4, "cx", (1, 2), ()),
        Operation(5, "rz", (2,), (math.pi / 5,)),
        Operation(6, "x", (0,), ()),
    ]
    return SimpleCircuit("worked_qpdg_example", "synthetic_method_figure", 3, ops)