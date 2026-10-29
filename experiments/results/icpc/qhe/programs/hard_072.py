import contextlib
from qiskit import QuantumCircuit
from qiskit.circuit import Gate

def gate_if_clbits(circuit, gate, qubits, condition_clbits):
    with contextlib.ExitStack() as stack:
        for index in condition_clbits:
            stack.enter_context(circuit.if_test((index, 1)))
        circuit.append(gate, qubits)
