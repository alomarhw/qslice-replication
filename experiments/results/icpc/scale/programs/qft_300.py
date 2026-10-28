import numpy as np
from qiskit import QuantumCircuit

n = 300
qc = QuantumCircuit(n, n)
for j in range(n):
    qc.h(j)
    for k in range(j + 1, n):
        qc.cp(np.pi / 2 ** (k - j), k, j)
for j in range(n // 2):
    qc.swap(j, n - j - 1)
qc.measure(range(n), range(n))
