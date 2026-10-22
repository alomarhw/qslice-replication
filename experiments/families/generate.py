"""Structure families (PROTOCOL_ICPC.md section 3.3), generated with fixed seeds.

F-ghz    GHZ preparation on n qubits (H q0, CX chain), then the last k CXs of the chain undone in
         reverse order; n in 3..10, k in 1..n-2.
F-w      W-state preparation on n qubits (RY cascade + controlled-RY + CX), then the last
         floor(n/2) preparation steps undone in reverse order; n in 3..8.
F-red    criterion q0 in superposition and m partners; each round entangles q0 with every partner
         (CX), disentangles (the same CXs in reverse) and re-entangles; m in 1..6, 1-3 rounds.
F-int    interleaved indirect entanglement on a chain q0-q1-...-q(L-1): H q0, CX(q_i, q_i+1) along
         the chain, then CX(q0, q1) undone; chain length L in 3..8.
F-inv    width w, a Hadamard layer and a CX ring on all qubits, then U U^dagger with U a seeded random
         circuit (depth d) on the first ceil(w/2) qubits; w in 4..10, d in {2, 5, 10, 20}.
F-depth  width 8, `depth` random layers (a random 1-qubit gate per qubit and CXs on a random
         matching); every third block of 5 layers is followed by its inverse (uncompute segment);
         depth in {10, 20, 40, 80, 160} x 5 seeds.
Seed 20261023 (per family and size). Every qubit is a criterion (families_run.py).
"""

from __future__ import annotations

import hashlib
from typing import Iterator, Tuple

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.random import random_circuit

SEED = 20261023
ONE_Q = ["h", "x", "y", "z", "s", "t", "sx"]


def _rng(tag: str) -> np.random.Generator:
    return np.random.default_rng(int(hashlib.sha256(f"{SEED}:{tag}".encode()).hexdigest()[:12], 16))


def f_ghz(n: int, k: int) -> QuantumCircuit:
    qc = QuantumCircuit(n)
    qc.h(0)
    chain = [(i, i + 1) for i in range(n - 1)]
    for c, t in chain:
        qc.cx(c, t)
    for c, t in reversed(chain[-k:]):
        qc.cx(c, t)
    return qc


def f_w(n: int) -> QuantumCircuit:
    steps = QuantumCircuit(n)
    steps.x(0)
    for i in range(n - 1):  # standard W cascade: move amplitude 1/(n-i) from qubit i to i+1
        theta = 2 * np.arccos(np.sqrt(1 / (n - i)))
        steps.cry(theta, i, i + 1)
        steps.cx(i + 1, i)
    qc = steps.copy()
    undo = steps.data[-(2 * (n // 2)):]  # the last floor(n/2) steps (2 instructions each)
    for inst in reversed(undo):
        qc.append(inst.operation.inverse(), inst.qubits)
    return qc


def f_red(m: int, rounds: int) -> QuantumCircuit:
    qc = QuantumCircuit(m + 1)
    qc.h(0)
    for _ in range(rounds):
        for p in range(1, m + 1):
            qc.cx(0, p)
        for p in reversed(range(1, m + 1)):
            qc.cx(0, p)
        for p in range(1, m + 1):
            qc.cx(0, p)
    return qc


def f_int(length: int) -> QuantumCircuit:
    qc = QuantumCircuit(length)
    qc.h(0)
    for i in range(length - 1):
        qc.cx(i, i + 1)
    qc.cx(0, 1)
    return qc


def f_inv(w: int, d: int) -> QuantumCircuit:
    qc = QuantumCircuit(w)
    for q in range(w):
        qc.h(q)
    for q in range(w):
        qc.cx(q, (q + 1) % w)
    sub = list(range((w + 1) // 2))
    seed = int(hashlib.sha256(f"{SEED}:F-inv:{w}:{d}".encode()).hexdigest()[:8], 16)
    u = random_circuit(len(sub), d, max_operands=2, seed=seed)
    qc.compose(u, qubits=sub, inplace=True)
    qc.compose(u.inverse(), qubits=sub, inplace=True)
    return qc


def f_depth(depth: int, seed: int) -> QuantumCircuit:
    rng = _rng(f"F-depth:{depth}:{seed}")
    n = 8
    qc = QuantumCircuit(n)
    block = []
    for layer in range(depth):
        lay = QuantumCircuit(n)
        for q in range(n):
            getattr(lay, ONE_Q[rng.integers(len(ONE_Q))])(q)
        perm = rng.permutation(n)
        for a, b in zip(perm[0::2], perm[1::2]):
            if rng.random() < 0.5:
                lay.cx(int(a), int(b))
        qc.compose(lay, inplace=True)
        block.append(lay)
        if len(block) == 5:
            if (layer // 5) % 3 == 2:  # every third block is followed by its inverse
                for lb in reversed(block):
                    qc.compose(lb.inverse(), inplace=True)
            block = []
    return qc


def families() -> Iterator[Tuple[str, str, QuantumCircuit]]:
    for n in range(3, 11):
        for k in range(1, n - 1):
            yield "F-ghz", f"n{n}_k{k}", f_ghz(n, k)
    for n in range(3, 9):
        yield "F-w", f"n{n}", f_w(n)
    for m in range(1, 7):
        for r in (1, 2, 3):
            yield "F-red", f"m{m}_r{r}", f_red(m, r)
    for length in range(3, 9):
        yield "F-int", f"L{length}", f_int(length)
    for w in range(4, 11):
        for d in (2, 5, 10, 20):
            yield "F-inv", f"w{w}_d{d}", f_inv(w, d)
    for depth in (10, 20, 40, 80, 160):
        for s in range(5):
            yield "F-depth", f"d{depth}_s{s}", f_depth(depth, s)
