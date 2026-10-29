from qiskit import QuantumCircuit

def create_quantum_circuit_based_h0_crz01_h1_cry10(theta):
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.crz(theta,0,1)
    qc.h(1)
    qc.cry(theta,1,0)
    return qc
