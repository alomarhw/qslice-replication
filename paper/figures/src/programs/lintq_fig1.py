from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
qreg = QuantumRegister(4)
creg = ClassicalRegister(3)
# Create a quantum circuit
circ = QuantumCircuit(qreg, creg)  # Bug 1: Oversized circuit
# Add gates and measurements to the circuit
for i in range(3):
    circ.h(i)
circ.measure(qreg[0], creg[0])
circ.ry(0.9, qreg[0])  # Bug 2: Operation after measurement
circ.measure([0, 1, 2], creg)
