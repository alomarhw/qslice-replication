from qiskit import QuantumCircuit
circuit = QuantumCircuit(3, 3)
circuit.ccx(0, 1, 2)
circuit.measure(0, 0)
circuit.measure(2, 2)
# Problem: Qubit 0 already measured
circuit.measure(0, 1)
