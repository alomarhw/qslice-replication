# A while_loop inside an if_test inside a for_loop.
from qiskit import QuantumCircuit

qc = QuantumCircuit(3, 2)
qc.h(0)
qc.measure(0, 0)
with qc.for_loop(range(2)):
    with qc.if_test((qc.clbits[0], 1)):
        qc.h(1)
        qc.measure(1, 1)
        with qc.while_loop((qc.clbits[1], 1)):
            qc.cx(1, 2)
            qc.h(1)
            qc.measure(1, 1)
qc.x(2)
