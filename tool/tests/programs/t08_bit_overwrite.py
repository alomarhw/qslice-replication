from qiskit import QuantumCircuit

qc = QuantumCircuit(3, 1)
qc.h(0)
qc.h(1)
qc.measure(0, 0)
qc.measure(1, 0)          # overwrites c0 before the condition reads it
with qc.if_test((qc.clbits[0], 1)):
    qc.x(2)
