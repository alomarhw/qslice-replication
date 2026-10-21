"""Checks of icpc/oracle_icpc.py against Qiskit, run before any ICPC experiment
(PROTOCOL_ICPC.md sections 3.4 and 3.5).

- joint reduced states rho_W agree with Statevector + partial_trace on random unitary circuits;
- prepared product inputs agree with Statevector of the prepared circuit;
- the 17-20 qubit path agrees with Statevector to 1e-12;
- the perturbation helpers do what section 2.1 says (insertion position, outcome flip, scope).

Usage (from experiments/): python tests/test_oracle_icpc.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.random import random_circuit
from qiskit.quantum_info import DensityMatrix, Statevector, partial_trace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from icpc import oracle_icpc as oi  # noqa: E402


def _ref_joint(qc, W):
    sv = Statevector(qc)
    return partial_trace(sv, [q for q in range(qc.num_qubits) if q not in W]).data


def check_joint(seed=7, n_circuits=40):
    rng = np.random.default_rng(seed)
    worst = 0.0
    for i in range(n_circuits):
        n = int(rng.integers(3, 8))
        qc = random_circuit(n, int(rng.integers(2, 8)), max_operands=3, seed=int(rng.integers(1 << 30)))
        for size in (1, 2, 3):
            W = sorted(rng.choice(n, size=size, replace=False).tolist())
            got = oi.joint_reduced_state(qc, W)
            ref = _ref_joint(qc, W)
            worst = max(worst, float(np.abs(got - ref).max()))
            assert abs(oi.uhlmann_fidelity(got, ref) - 1) < 1e-9
    return worst


def check_inputs(seed=11, n_circuits=30):
    rng = np.random.default_rng(seed)
    worst = 0.0
    for _ in range(n_circuits):
        n = int(rng.integers(2, 7))
        qc = random_circuit(n, 5, max_operands=2, seed=int(rng.integers(1 << 30)))
        prep = oi.haar_product_input(n, rng)
        pq = oi.with_input(qc, prep)
        got = oi.reduced_states(pq, range(n))
        for q in range(n):
            ref = _ref_joint(pq, [q])
            worst = max(worst, float(np.abs(got[q] - ref).max()))
    return worst


def check_large(seed=13):
    rng = np.random.default_rng(seed)
    worst = 0.0
    for n in (17, 18, 20):
        qc = random_circuit(n, 4, max_operands=2, seed=int(rng.integers(1 << 30)))
        got = oi.reduced_states(qc, [0, n // 2, n - 1], max_qubits=20)
        for q in (0, n // 2, n - 1):
            worst = max(worst, float(np.abs(got[q] - _ref_joint(qc, [q])).max()))
    assert worst < 1e-12, worst
    return worst


def check_perturbations():
    # insertion lands right after instruction k, on its qubits
    qc = QuantumCircuit(2); qc.h(0); qc.cx(0, 1); qc.x(1)
    u = oi.haar_unitary(4, np.random.default_rng(1))
    p = oi.insert_unitary_after(qc, 1, u)
    assert [i.operation.name for i in p.data] == ["h", "cx", "unitary", "x"]
    assert [p.find_bit(b).index for b in p.data[2].qubits] == [0, 1]
    # Bell q0 is maximally mixed: no product of local unitaries changes rho_q0, a joint one can
    bell = QuantumCircuit(2); bell.h(0); bell.cx(0, 1)
    base = oi.reduced_states(bell, [0])[0]
    rng = np.random.default_rng(3)
    local = np.kron(oi.haar_unitary(2, rng), oi.haar_unitary(2, rng))
    assert oi.uhlmann_fidelity(oi.reduced_states(oi.insert_unitary_after(bell, 1, local), [0])[0], base) > 1 - 1e-9
    joint_changed = any(oi.uhlmann_fidelity(oi.reduced_states(oi.insert_unitary_after(
        bell, 1, oi.haar_unitary(4, rng)), [0])[0], base) < 1 - 1e-6 for _ in range(2))
    assert joint_changed
    # outcome flip: inverts conditions reading the bit, stops at the next write of the bit
    fb = QuantumCircuit(2, 1); fb.h(1); fb.measure(1, 0)
    with fb.if_test((fb.clbits[0], 1)):
        fb.x(0)
    fb.measure(1, 0)
    with fb.if_test((fb.clbits[0], 1)):
        fb.z(0)
    f = oi.flip_measurement_outcome(fb, 1)
    conds = [i.operation.condition[1] for i in f.data if i.operation.name == "if_else"]
    assert conds == [0, 1], conds
    nothing = QuantumCircuit(1, 1); nothing.measure(0, 0)
    assert oi.flip_measurement_outcome(nothing, 0) is None
    return True


def main() -> int:
    print(f"joint rho_W vs Statevector/partial_trace, max abs error: {check_joint():.2e}")
    print(f"prepared product inputs, max abs error: {check_inputs():.2e}")
    print(f"17-20 qubits, max abs error: {check_large():.2e}")
    print(f"perturbation helpers: {'OK' if check_perturbations() else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
