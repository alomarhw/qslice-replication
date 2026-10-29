from qiskit import QuantumCircuit

def x_measurement(circuit, qubit, clbit):
    circuit.h(qubit)
    circuit.measure(qubit, clbit)
