from qiskit import QuantumCircuit
import numpy as np

n = 5
qc = QuantumCircuit(n, n)
targets = []
for k in range(n):
    if k % 2 == 0:
        targets.append(k)
qc.h(targets)
qc.cx(0, [1, 2, 3])
pairs = [(i, (i + 1) % n) for i in range(n)]
for a, b in pairs:
    qc.cz(a, b)
angles = [np.pi / (2 ** j) for j in range(n)]
for j, th in enumerate(angles):
    qc.rz(th, j)
qc.swap(0, n - 1)
qc.mcx([0, 1, 2], 4)
qc.measure(range(n), range(n))
