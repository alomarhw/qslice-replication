import math
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

N_QUBITS = 12


def qft_rotations(circuit, n):
    if n == 0:
        return circuit
    n -= 1
    circuit.h(n)
    for qubit in range(n):
        circuit.cp(math.pi / 2 ** (n - qubit), qubit, n)
    qft_rotations(circuit, n)


def swap_registers(circuit, n):
    for qubit in range(n // 2):
        circuit.swap(qubit, n - qubit - 1)
    return circuit


def qft(circuit, n):
    qft_rotations(circuit, n)
    swap_registers(circuit, n)
    return circuit


def inverse_qft(circuit, n):
    for qubit in range(n // 2):
        circuit.swap(qubit, n - qubit - 1)
    for j in range(n):
        for m in range(j):
            circuit.cp(-math.pi / float(2 ** (j - m)), m, j)
        circuit.h(j)
    return circuit


q = QuantumRegister(N_QUBITS, "q")
c = ClassicalRegister(N_QUBITS, "c")
qc = QuantumCircuit(q, c)
value = 1234
for i in range(N_QUBITS):
    if (value >> i) & 1:
        qc.x(q[i])
qft(qc, N_QUBITS)
qc.barrier()
inverse_qft(qc, N_QUBITS)
qc.measure(q, c)
