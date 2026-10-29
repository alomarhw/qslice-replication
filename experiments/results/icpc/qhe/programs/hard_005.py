from qiskit import QuantumCircuit

def create_state_prep():
    qc = QuantumCircuit(2)
    qc.prepare_state("01")
    return qc
