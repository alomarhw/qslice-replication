from qiskit import QuantumCircuit
import qiskit.qasm3

def convert_quantum_circuit_to_qasm_string(circuit):
    qasm_str = qiskit.qasm3.dumps(circuit)
    return qasm_str
