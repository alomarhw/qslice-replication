from qiskit.circuit.random import random_circuit
from qiskit import QuantumCircuit

def random_circuit_depth():
    circuit = random_circuit(4, 3, measure=True, seed = 17)
    return circuit
