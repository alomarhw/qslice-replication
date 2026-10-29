from qiskit import QuantumCircuit
from qiskit.circuit.library import U3Gate

def controlled_custom_unitary_circuit():
    qc = QuantumCircuit(2)
    custom_gate = U3Gate(0.3, 0.2, 0.1).control()
    qc.append(custom_gate, [0, 1])
    return qc
