from qiskit import QuantumCircuit

def dj_constant_oracle():
    oracle = QuantumCircuit(3)
    oracle.x(2)
    return oracle
