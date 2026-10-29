from qiskit.circuit.library import CDKMRippleCarryAdder
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

def create_ripple_carry_adder_circuit(num_state_qubits, kind):
    adder = CDKMRippleCarryAdder(num_state_qubits, kind)
    qc = QuantumCircuit(adder.num_qubits)
    qc.append(adder.to_instruction(), range(adder.num_qubits))
    return qc
