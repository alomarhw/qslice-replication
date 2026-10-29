# Classical feedback: the loop bit is measured from q1, which q0 influences through a CNOT in the body.
from qiskit import QuantumCircuit

qc = QuantumCircuit(3, 1)
qc.ry(1.2, 0)
qc.h(1)
qc.measure(1, 0)
with qc.while_loop((qc.clbits[0], 1)):
    qc.reset(1)
    qc.cx(0, 1)
    qc.h(1)
    qc.measure(1, 0)
qc.cx(1, 2)
qc.h(0)
