from qiskit import QuantumCircuit

def remove_gate_in_position(circuit, position):
    del circuit.data[position]
    return circuit
