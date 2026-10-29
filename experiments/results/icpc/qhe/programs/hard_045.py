from qiskit.quantum_info.random import random_clifford

def get_random_clifford(n_qubits):
    return random_clifford(num_qubits=n_qubits)
