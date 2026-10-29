# A switch on a two-bit register, with a default case.
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

q = QuantumRegister(4, "q")
c = ClassicalRegister(2, "c")
qc = QuantumCircuit(q, c)
qc.h(q[0])
qc.h(q[1])
qc.ry(0.4, q[3])
qc.measure(q[0], c[0])
qc.measure(q[1], c[1])
with qc.switch(c) as case:
    with case(0):
        qc.x(q[2])
    with case(1, 2):
        qc.cx(q[3], q[2])
    with case(case.DEFAULT):
        qc.h(q[2])
qc.z(q[3])
