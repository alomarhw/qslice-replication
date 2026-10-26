from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

hops = 4
q = QuantumRegister(1 + 2 * hops, "q")
c = ClassicalRegister(2 * hops, "c")
out = ClassicalRegister(1, "out")
qc = QuantumCircuit(q, c, out)
qc.u(0.4, 0.2, 0.1, q[0])
src = 0
for h in range(hops):
    a, b = 1 + 2 * h, 2 + 2 * h
    qc.h(q[a])
    qc.cx(q[a], q[b])
    qc.cx(q[src], q[a])
    qc.h(q[src])
    qc.measure(q[src], c[2 * h])
    qc.measure(q[a], c[2 * h + 1])
    with qc.if_test((c[2 * h + 1], 1)):
        qc.x(q[b])
    with qc.if_test((c[2 * h], 1)):
        qc.z(q[b])
    src = b
qc.measure(q[src], out[0])
