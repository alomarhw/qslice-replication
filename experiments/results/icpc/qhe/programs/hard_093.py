from qiskit.synthesis import synth_clifford_full
from qiskit.quantum_info.random import random_clifford

def synthesize_clifford_circuit(n_qubits):
    qc = random_clifford(n_qubits, seed=1234)
    synthesized_qc = synth_clifford_full(qc)
    return synthesized_qc
