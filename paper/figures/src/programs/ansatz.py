import numpy as np
from qiskit import QuantumCircuit

n = 3
layers = 2
rng = np.random.default_rng(7)

qc = QuantumCircuit(n + 1, n + 1)

for layer in range(layers):
    for qubit in range(n):
        qc.ry(float(rng.uniform(0, np.pi)), qubit)
        qc.rz(float(rng.uniform(0, 2 * np.pi)), qubit)
    for qubit in range(n - 1):
        qc.cx(qubit, qubit + 1)

qc.h(n)                          # auxiliary qubit
qc.measure(n, n)                 # mid-circuit measurement
with qc.if_test((qc.clbits[n], 1)):
    qc.x(0)                      # flip conditioned on it
qc.measure(range(n), range(n))
