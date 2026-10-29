# A for_loop whose body passes state one qubit along per iteration: q0 reaches q3 only after three iterations.
from qiskit import QuantumCircuit

qc = QuantumCircuit(4)
qc.ry(1.1, 0)
with qc.for_loop(range(3)):
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.cx(2, 3)
    qc.swap(0, 1)
qc.h(3)
