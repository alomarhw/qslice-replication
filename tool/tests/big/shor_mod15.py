import math
from qiskit import QuantumCircuit

N_COUNT = 8
a = 7


def c_amod15(circ, ctrl, base, power, offset):
    for _ in range(power):
        if base in [2, 13]:
            circ.cswap(ctrl, offset + 2, offset + 3)
            circ.cswap(ctrl, offset + 1, offset + 2)
            circ.cswap(ctrl, offset + 0, offset + 1)
        if base in [7, 8]:
            circ.cswap(ctrl, offset + 0, offset + 1)
            circ.cswap(ctrl, offset + 1, offset + 2)
            circ.cswap(ctrl, offset + 2, offset + 3)
        if base in [4, 11]:
            circ.cswap(ctrl, offset + 1, offset + 3)
            circ.cswap(ctrl, offset + 0, offset + 2)
        if base in [7, 11, 13]:
            for q in range(4):
                circ.cx(ctrl, offset + q)


def qft_dagger(circ, n):
    for qubit in range(n // 2):
        circ.swap(qubit, n - qubit - 1)
    for j in range(n):
        for m in range(j):
            circ.cp(-math.pi / float(2 ** (j - m)), m, j)
        circ.h(j)


qc = QuantumCircuit(N_COUNT + 4, N_COUNT)
for q in range(N_COUNT):
    qc.h(q)
qc.x(N_COUNT)
for q in range(N_COUNT):
    c_amod15(qc, q, a, 2 ** q, N_COUNT)
qft_dagger(qc, N_COUNT)
qc.measure(range(N_COUNT), range(N_COUNT))
