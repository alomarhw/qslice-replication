# if_test with an else branch: both branches are conditioned on the measured bit.
from qiskit import QuantumCircuit

qc = QuantumCircuit(3, 1)
qc.ry(0.9, 0)
qc.h(2)
qc.measure(0, 0)
with qc.if_test((qc.clbits[0], 1)) as else_:
    qc.x(1)
with else_:
    qc.cx(2, 1)
qc.h(2)
