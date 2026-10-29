from qiskit import QuantumCircuit

def create_state_prep(num_qubits):
    qc = QuantumCircuit(num_qubits)
    qc.prepare_state(1)
    return qc
