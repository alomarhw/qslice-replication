from qiskit import QuantumCircuit

def count_instructions(circuit):
    return len(circuit.data)
