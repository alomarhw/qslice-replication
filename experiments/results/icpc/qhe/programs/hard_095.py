from qiskit import QuantumCircuit
from qiskit.transpiler.passes import RemoveBarriers

def remove_barrier(circuit):
    return  RemoveBarriers()(circuit)
