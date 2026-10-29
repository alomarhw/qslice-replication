from qiskit.circuit.library import LinearFunction
from qiskit.synthesis.linear import random_invertible_binary_matrix

def get_random_linear_function(n_qubits, seed):
    return LinearFunction(random_invertible_binary_matrix(num_qubits=n_qubits, seed=seed))
