from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

q = QuantumRegister(3, "q")
c = ClassicalRegister(2, "c")
qc = QuantumCircuit(q, c)

qc.ry(0.9, 0)
qc.h(1)
qc.cx(1, 2)
qc.cx(0, 1)
qc.h(0)
qc.measure(0, 0)
qc.measure(1, 1)
with qc.if_test((c[1], 1)):
    qc.x(2)
with qc.if_test((c[0], 1)):
    qc.z(2)
