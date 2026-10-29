from qiskit import QuantumCircuit
from qiskit.circuit import Gate

def count_gates(circuit):
    count = 0
    for inst in circuit.data:
        if isinstance(inst.operation, Gate):
            count += 1
    return count
