from qiskit import QuantumCircuit

secret = "110100101101"
n = len(secret)
bv = QuantumCircuit(n + 1, n)
bv.x(n)
bv.h(n)
for i in range(n):
    bv.h(i)
bv.barrier()
for i, s in enumerate(reversed(secret)):
    if s == "1":
        bv.cx(i, n)
bv.barrier()
for i in range(n):
    bv.h(i)
for i in range(n):
    bv.measure(i, i)
