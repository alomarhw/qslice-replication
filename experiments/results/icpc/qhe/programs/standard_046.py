from qiskit.circuit.library import LinearFunction
from qiskit.synthesis.linear import random_invertible_binary_matrix
def get_random_linear_function(n_qubits, seed):
    """ Generate a random linear function circuit using the input parameters n_qubits and seed, and the random_invertible_binary_matrix method.
    """
    return LinearFunction(random_invertible_binary_matrix(num_qubits=n_qubits, seed=seed))
