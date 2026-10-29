from qiskit import QuantumCircuit
from qiskit.quantum_info import random_clifford, Operator

def equivalent_clifford_circuit(circuit, n):
    op_or = Operator(circuit)
    num_qubits = circuit.num_qubits
    qc_list = []
    counter = 0
    while counter< n:
        qc = random_clifford(num_qubits).to_circuit()
        op_qc = Operator(qc)
        if op_qc.equiv(op_or, rtol = 0.4, atol = 0.4) == True:
            counter += 1
            qc_list.append(qc)
    return qc_list
