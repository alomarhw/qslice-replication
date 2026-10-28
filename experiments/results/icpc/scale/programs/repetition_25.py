from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

d = 25
rounds = 10
data = QuantumRegister(d, "data")
anc = QuantumRegister(d - 1, "anc")
syn = ClassicalRegister(d - 1, "syn")
qc = QuantumCircuit(data, anc, syn)
qc.x(data[0])
for r in range(rounds):
    for i in range(d - 1):
        qc.cx(data[i], anc[i])
        qc.cx(data[i + 1], anc[i])
    for i in range(d - 1):
        qc.measure(anc[i], syn[i])
        qc.reset(anc[i])
