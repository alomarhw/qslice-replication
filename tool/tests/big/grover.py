import math
from qiskit import QuantumCircuit

n = 7
marked = "1011010"
iterations = math.floor(math.pi / 4 * math.sqrt(2 ** n))


def oracle(qc, n, marked):
    for i, bit in enumerate(reversed(marked)):
        if bit == "0":
            qc.x(i)
    qc.h(n - 1)
    qc.mcx(list(range(n - 1)), n - 1)
    qc.h(n - 1)
    for i, bit in enumerate(reversed(marked)):
        if bit == "0":
            qc.x(i)


def diffuser(qc, n):
    qc.h(range(n))
    qc.x(range(n))
    qc.h(n - 1)
    qc.mcx(list(range(n - 1)), n - 1)
    qc.h(n - 1)
    qc.x(range(n))
    qc.h(range(n))


qc = QuantumCircuit(n, n)
qc.h(range(n))
for _ in range(iterations):
    oracle(qc, n, marked)
    diffuser(qc, n)
qc.measure(range(n), range(n))
