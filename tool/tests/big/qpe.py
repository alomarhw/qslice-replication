import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

t = 8
phase = 1 / 3
counting = QuantumRegister(t, "count")
target = QuantumRegister(1, "psi")
out = ClassicalRegister(t, "out")
qc = QuantumCircuit(counting, target, out)
qc.x(target[0])
for k in range(t):
    qc.h(counting[k])
repetitions = 1
for k in range(t):
    for _ in range(repetitions):
        qc.cp(2 * np.pi * phase, counting[k], target[0])
    repetitions *= 2


def qft_dagger(circ, reg):
    n = len(reg)
    for j in range(n // 2):
        circ.swap(reg[j], reg[n - j - 1])
    for j in range(n):
        for m in range(j):
            circ.cp(-np.pi / float(2 ** (j - m)), reg[m], reg[j])
        circ.h(reg[j])


qft_dagger(qc, counting)
qc.measure(counting, out)
