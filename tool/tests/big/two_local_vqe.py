import numpy as np
from qiskit import QuantumCircuit

num_qubits = 9
reps = 4
entanglement = "circular"
rotation_blocks = ["ry", "rz"]
rng = np.random.default_rng(11)
theta = rng.uniform(-np.pi, np.pi, size=(reps + 1) * len(rotation_blocks) * num_qubits)


def entangler_map(kind, n):
    if kind == "linear":
        return [(i, i + 1) for i in range(n - 1)]
    if kind == "circular":
        return [(n - 1, 0)] + [(i, i + 1) for i in range(n - 1)]
    return [(i, j) for i in range(n) for j in range(i + 1, n)]


qc = QuantumCircuit(num_qubits)
k = 0
for r in range(reps + 1):
    for gate in rotation_blocks:
        for q in range(num_qubits):
            getattr(qc, gate)(theta[k], q)
            k += 1
    if r < reps:
        for (i, j) in entangler_map(entanglement, num_qubits):
            qc.cx(i, j)
qc.measure_all()
