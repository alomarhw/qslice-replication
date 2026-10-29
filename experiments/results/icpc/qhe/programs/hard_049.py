from qiskit import QuantumCircuit

def simple_elitzur_vaidman():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0,1)
    circuit.h(0)
    return circuit
