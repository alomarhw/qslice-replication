from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

def create_uniform_superposition(n: int) -> Statevector:
    qc = QuantumCircuit(n)
    qc.h(range(n))
    return Statevector(qc)
