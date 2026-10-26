# Unknown iteration count (k from the command line): a dependence reaches q3 from cx(0,1) only three iterations back.
from qiskit import QuantumCircuit
import sys
k = int(sys.argv[1])
qc = QuantumCircuit(4)
qc.h(0)
for _ in range(k):
    qc.cx(2, 3)
    qc.cx(1, 2)
    qc.cx(0, 1)
