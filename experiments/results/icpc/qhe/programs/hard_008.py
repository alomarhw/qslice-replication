from qiskit.circuit import QuantumCircuit, Parameter

def rx_gate(value=None):
    theta = Parameter("theta")
    quantum_circuit = QuantumCircuit(1)
    quantum_circuit.rx(theta, 0)
    if value is not None:
        return quantum_circuit.assign_parameters({theta: value})
    return quantum_circuit
