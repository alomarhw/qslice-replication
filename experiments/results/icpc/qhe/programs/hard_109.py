from qiskit.circuit import QuantumCircuit, Parameter

def circuit():
    qc = QuantumCircuit(1)
    qc.h(0)
    theta = Parameter('th')
    qc.rz(theta,0)
    return qc
    