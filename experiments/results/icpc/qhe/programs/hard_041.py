from qiskit.quantum_info.operators import Operator, Pauli
import numpy as np

def compose_op():
    op = Operator(np.eye(2 ** 3))
    YX = Operator(Pauli('YX'))
    composition = op.compose(YX, qargs=[0, 2], front=True)
    return composition
