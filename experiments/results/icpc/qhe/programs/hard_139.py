from qiskit.quantum_info import schmidt_decomposition

def schmidt_test(data, qargs_B):
    return schmidt_decomposition(data, qargs_B)
