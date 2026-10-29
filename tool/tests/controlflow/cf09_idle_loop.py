# The loop never touches q2, whose slice should not need it.
from qiskit import QuantumCircuit

qc = QuantumCircuit(3, 1)
qc.h(0)
qc.ry(0.3, 2)
qc.measure(0, 0)
with qc.while_loop((qc.clbits[0], 1)):
    qc.h(0)
    qc.cx(0, 1)
    qc.measure(0, 0)
qc.x(2)
