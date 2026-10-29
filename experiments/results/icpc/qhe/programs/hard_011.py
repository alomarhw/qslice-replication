from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

def get_statevector(circuit):
    sv = Statevector.from_instruction(circuit)
    return sv
