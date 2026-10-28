from qiskit import QuantumCircuit
qc = QuantumCircuit(3, 3)
qc.x(0)
qc.h(1)
qc.cx(1, 2)
qc.cx(0, 1)
qc.h(0)
qc.measure(0, 0)
qc.measure(1, 1)
qc.cx(1, 2)  # Problematic operation
qc.cz(0, 2)  # Problematic operation
