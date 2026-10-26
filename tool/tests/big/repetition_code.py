from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

d = 5
data = QuantumRegister(d, "data")
anc = QuantumRegister(d - 1, "anc")
syn = ClassicalRegister(d - 1, "syn")
final = ClassicalRegister(d, "final")
qc = QuantumCircuit(data, anc, syn, final)
qc.ry(0.7, data[0])
for i in range(1, d):
    qc.cx(data[0], data[i])
error_on = 2
qc.x(data[error_on])
for i in range(d - 1):
    qc.cx(data[i], anc[i])
    qc.cx(data[i + 1], anc[i])
    qc.measure(anc[i], syn[i])
for i in range(d - 1):
    with qc.if_test((syn[i], 1)):
        qc.x(anc[i])
for i in range(1, d - 1):
    with qc.if_test((syn[i - 1], 1)):
        with qc.if_test((syn[i], 1)):
            qc.x(data[i])
for i in reversed(range(1, d)):
    qc.cx(data[0], data[i])
qc.measure(data, final)
