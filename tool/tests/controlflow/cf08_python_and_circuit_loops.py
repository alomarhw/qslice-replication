# A Python loop builds the circuit around an in-circuit while_loop.
from qiskit import QuantumCircuit

n = 3
qc = QuantumCircuit(n + 1, 1)
for k in range(n):
    qc.h(k)
qc.measure(n - 1, 0)
with qc.while_loop((qc.clbits[0], 1)):
    for k in range(n - 1):
        qc.cx(k, k + 1)
    qc.h(n - 1)
    qc.measure(n - 1, 0)
qc.cx(0, n)
