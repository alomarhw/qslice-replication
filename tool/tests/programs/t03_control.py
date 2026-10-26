from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit.library import XGate, HGate

q = QuantumRegister(3)
c = ClassicalRegister(3)
qc = QuantumCircuit(q, c)
qc.h(0)
qc.measure(0, 0)
with qc.if_test((c[0], 1)):
    qc.x(1)
    qc.cx(1, 2)
qc.append(XGate(), [q[2]])
qc.append(HGate(), [2])
sub = QuantumCircuit(2)
sub.h(0)
sub.cx(0, 1)
qc.compose(sub, qubits=[1, 2], inplace=True)
mode = "full"
if mode == "full":
    qc.ry(0.3, 0)
elif mode == "half":
    qc.ry(0.1, 0)
else:
    qc.ry(0.0, 0)
i = 0
while i < 3:
    qc.t(i)
    i += 1
qc.measure([1, 2], [1, 2])
