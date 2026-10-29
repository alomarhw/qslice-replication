from qiskit import QuantumCircuit

def quantum_circuit_with_delay():
    qc = QuantumCircuit(1)
    qc.h(0)
    delay_duration = 100
    qc.delay(delay_duration, 0, unit="dt")
    qc.h(0)
    return qc
