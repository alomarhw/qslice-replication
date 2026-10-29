# Repeat until success: q0 is re-prepared until its measurement gives 0; q1 is entangled with q0 inside the loop.
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

q = QuantumRegister(3, "q")
c = ClassicalRegister(2, "c")
qc = QuantumCircuit(q, c)
qc.h(q[0])
qc.ry(0.7, q[2])
qc.measure(q[0], c[0])
with qc.while_loop((c[0], 1)):
    qc.reset(q[0])
    qc.h(q[0])
    qc.cx(q[0], q[1])
    qc.measure(q[0], c[0])
qc.x(q[2])
