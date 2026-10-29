from qiskit.circuit import QuantumCircuit

def inv_circuit(n):
    qc = QuantumCircuit(n)
    for i in range(2):
        qc.h(i+1)

    for i in range(2):
        qc.cx(i+1, i+2+1)
    
    return qc.inverse()
