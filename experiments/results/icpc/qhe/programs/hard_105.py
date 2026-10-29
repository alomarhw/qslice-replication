from qiskit import QuantumCircuit
from qiskit.quantum_info import CNOTDihedral

def initialize_cnot_dihedral():
    circ = QuantumCircuit(2)
    # Apply gates
    circ.cx(0, 1)
    circ.t(0)
    elem = CNOTDihedral(circ)

    return elem
