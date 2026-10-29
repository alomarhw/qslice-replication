# The loop body acts on q1 as a CNOT control, so q1 changes by phase kickback from q2 in |->; q0 decides the loop.
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

q = QuantumRegister(3, "q")
c = ClassicalRegister(1, "c")
qc = QuantumCircuit(q, c)
qc.x(q[2])
qc.h(q[2])
qc.h(q[1])
qc.h(q[0])
qc.measure(q[0], c[0])
with qc.while_loop((c[0], 1)):
    qc.cx(q[1], q[2])
    qc.h(q[0])
    qc.measure(q[0], c[0])
qc.h(q[1])
