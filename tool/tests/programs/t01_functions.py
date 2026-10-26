from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister


def bell(circ, a, b):
    circ.h(a)
    circ.cx(a, b)
    return circ


def ladder(circ, qubits):
    for i in range(len(qubits) - 1):
        circ.cx(qubits[i], qubits[i + 1])


q = QuantumRegister(4, "q")
anc = QuantumRegister(2, "anc")
c = ClassicalRegister(4, "c")
qc = QuantumCircuit(q, anc, c)
bell(qc, q[0], q[1])
ladder(qc, [q[1], q[2], q[3], anc[0]])
qc.ccx(q[0], q[1], anc[1])
qc.h(q)
qc.measure(q, c)
