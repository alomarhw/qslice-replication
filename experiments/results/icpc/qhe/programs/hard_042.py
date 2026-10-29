from qiskit.quantum_info.operators import Operator, Pauli

def combine_op():
    XX = Operator(Pauli('XX'))
    YY = Operator(Pauli('YY'))
    ZZ = Operator(Pauli('ZZ'))

    op = 0.5 * (XX + YY - 3 * ZZ)
    return op
