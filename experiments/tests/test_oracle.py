"""Checks of the exact oracle against independent references. Run: python tests/test_oracle.py"""

import sys
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.random import random_circuit
from qiskit.quantum_info import DensityMatrix, Statevector, partial_trace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.oracle import fidelity, reduced_states  # noqa: E402


def ref_unitary(qc, q):
    sv = Statevector(qc)
    return partial_trace(sv, [i for i in range(qc.num_qubits) if i != q]).data


def test_random_unitary(n_trials=60):
    rng = np.random.default_rng(1)
    worst = 0.0
    for t in range(n_trials):
        n = int(rng.integers(2, 7))
        qc = random_circuit(n, depth=int(rng.integers(2, 12)), max_operands=3, seed=int(rng.integers(1e9)))
        got = reduced_states(qc, range(n))
        for q in range(n):
            worst = max(worst, np.abs(got[q] - ref_unitary(qc, q)).max())
    assert worst < 1e-10, worst
    return worst


def teleport(theta, phi):
    qc = QuantumCircuit(3, 2)
    qc.ry(theta, 0); qc.rz(phi, 0)
    qc.h(1); qc.cx(1, 2); qc.cx(0, 1); qc.h(0)
    qc.measure(0, 0); qc.measure(1, 1)
    with qc.if_test((qc.clbits[1], 1)):
        qc.x(2)
    with qc.if_test((qc.clbits[0], 1)):
        qc.z(2)
    return qc


def test_teleportation():
    worst = 0.0
    for theta, phi in [(0.3, 1.1), (1.9, -0.4), (np.pi, 0.0), (0.0, 0.0), (2.5, 2.5)]:
        ref = QuantumCircuit(1); ref.ry(theta, 0); ref.rz(phi, 0)
        want = DensityMatrix(ref).data
        got = reduced_states(teleport(theta, phi), [2])[2]
        worst = max(worst, np.abs(got - want).max())
        # without the corrections, q2 must be maximally mixed
        qc = teleport(theta, phi); qc.data = [i for i in qc.data if i.operation.name != "if_else"]
        mixed = reduced_states(qc, [2])[2]
        assert np.abs(mixed - np.eye(2) / 2).max() < 1e-10
    assert worst < 1e-10, worst
    return worst


def test_reset_and_midcircuit():
    qc = QuantumCircuit(2, 1)
    qc.h(0); qc.cx(0, 1); qc.reset(0)          # q0 back to |0>, q1 left maximally mixed
    got = reduced_states(qc, [0, 1])
    assert np.abs(got[0] - np.diag([1, 0])).max() < 1e-12
    assert np.abs(got[1] - np.eye(2) / 2).max() < 1e-12
    qc = QuantumCircuit(1, 1)
    qc.h(0); qc.measure(0, 0); qc.h(0)         # mid-circuit measurement then H: |0>,|1> -> |+>,|->
    got = reduced_states(qc, [0])[0]
    assert np.abs(got - np.eye(2) / 2).max() < 1e-12
    qc = QuantumCircuit(1, 1)
    qc.h(0); qc.measure(0, 0)                  # terminal measurement dephases |+>
    got = reduced_states(qc, [0])[0]
    assert np.abs(got - np.eye(2) / 2).max() < 1e-12
    assert abs(fidelity(np.diag([1, 0]), np.eye(2) / 2) - 0.5) < 1e-12


if __name__ == "__main__":
    print("random unitary circuits, max abs error:", test_random_unitary())
    print("teleportation (with feedback), max abs error:", test_teleportation())
    test_reset_and_midcircuit()
    print("reset / mid-circuit / terminal measurement: OK")
