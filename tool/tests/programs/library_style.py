# Library-style module: circuits are built only inside functions and a class that the file never calls.
from qiskit import QuantumCircuit


def ghz(n):
    qc = QuantumCircuit(n)
    qc.h(0)
    for i in range(n - 1):
        qc.cx(i, i + 1)
    return qc


class Teleporter:
    def build(self):
        qc = QuantumCircuit(3, 2)
        qc.h(1)
        qc.cx(1, 2)
        qc.cx(0, 1)
        qc.h(0)
        qc.measure([0, 1], [0, 1])
        return qc
