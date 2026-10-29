from qiskit.circuit import QuantumCircuit, Parameter

def circuit():
    qc = QuantumCircuit(1)
    p1 = Parameter("p1")
    p2 = Parameter("p2")
    qc.rx(p1,0)
    qc.ry(p2,0)
    return qc
