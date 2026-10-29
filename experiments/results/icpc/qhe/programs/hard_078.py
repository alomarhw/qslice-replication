from qiskit import QuantumCircuit
from qiskit.circuit.library import QFT

def qft_no_swaps(num_qubits):
    qft = QFT(num_qubits=num_qubits, do_swaps=False, inverse=True)
    return qft
