from qiskit import QuantumCircuit

def create_unitary_from_matrix():
    matrix = [[0, 0, 0, 1], [0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0]]
    circuit = QuantumCircuit(2)
    circuit.unitary(matrix, [0, 1])
    return circuit
