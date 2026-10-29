# A for_loop over a known index set with a loop parameter as rotation angle.
from qiskit import QuantumCircuit

qc = QuantumCircuit(3, 1)
qc.h(0)
with qc.for_loop(range(3)) as i:
    qc.rx(i, 1)
    qc.cx(1, 2)
qc.cz(0, 1)
qc.measure(2, 0)
