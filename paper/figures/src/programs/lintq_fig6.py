from qiskit import QuantumCircuit
qc = QuantumCircuit(2, 2)
qc.h(1)
qc.cx(1, 0)
qc.measure(0, 0)
qc.measure(1, 1)
qc.z(0)  # Problem: Qubit 0 has collapsed
qc.measure(0, 0)
