from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

n = 8
a = QuantumRegister(n, "a")
b = QuantumRegister(n, "b")
cin = QuantumRegister(1, "cin")
cout = QuantumRegister(1, "cout")
res = ClassicalRegister(n + 1, "res")
qc = QuantumCircuit(cin, a, b, cout, res)

x_val, y_val = 0b10110101, 0b01101110
for i in range(n):
    if (x_val >> i) & 1:
        qc.x(a[i])
    if (y_val >> i) & 1:
        qc.x(b[i])


def majority(circ, c, y, x):
    circ.cx(x, y)
    circ.cx(x, c)
    circ.ccx(c, y, x)


def unmajority(circ, c, y, x):
    circ.ccx(c, y, x)
    circ.cx(x, c)
    circ.cx(c, y)


majority(qc, cin[0], b[0], a[0])
for i in range(n - 1):
    majority(qc, a[i], b[i + 1], a[i + 1])
qc.cx(a[n - 1], cout[0])
for i in reversed(range(n - 1)):
    unmajority(qc, a[i], b[i + 1], a[i + 1])
unmajority(qc, cin[0], b[0], a[0])
for i in range(n):
    qc.measure(b[i], res[i])
qc.measure(cout[0], res[n])
