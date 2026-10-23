import numpy as np
from qiskit import QuantumCircuit

n = 3
layers = 2
rng = np.random.default_rng(7)

qc = QuantumCircuit(n, n)

for layer in range(layers):
    for qubit in range(n):
        qc.ry(float(rng.uniform(0, np.pi)), qubit)
        qc.rz(float(rng.uniform(0, 2 * np.pi)), qubit)
    for qubit in range(n - 1):
        qc.cx(qubit, qubit + 1)

qc.measure(range(n), range(n))
