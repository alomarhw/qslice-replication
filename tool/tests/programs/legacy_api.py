# Old Qiskit API (pre-1.0): cannot run on Qiskit 2.x; checked against a hand-written expected trace.
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, execute, Aer
import math

q = QuantumRegister(3, "q")
c = ClassicalRegister(3, "c")
qc = QuantumCircuit(q, c)
qc.u3(math.pi / 2, 0, math.pi, q[0])
qc.u1(math.pi / 4, q[1])
qc.cnot(q[0], q[1])
qc.toffoli(q[0], q[1], q[2])
qc.iden(q[2])
qc.measure(q[0], c[0])
qc.x(q[2]).c_if(c, 1)
qc.cu1(math.pi / 8, q[1], q[2])
qc.measure(q, c)
backend = Aer.get_backend("qasm_simulator")
result = execute(qc, backend, shots=1024).result()
counts = result.get_counts(qc)
