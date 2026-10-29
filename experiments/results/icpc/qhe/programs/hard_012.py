from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator
import numpy as np

def get_unitary() -> np.ndarray:
    circ = QuantumCircuit(2)
    circ.h(0)
    circ.cx(0, 1)
    return Operator.from_circuit(circ).to_matrix()