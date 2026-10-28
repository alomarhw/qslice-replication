from qiskit import QuantumCircuit

n = 20000
p = 4
gammas = [0.1 * (k + 1) for k in range(p)]
betas = [0.8 - 0.1 * k for k in range(p)]
qc = QuantumCircuit(n)
qc.h(range(n))
for layer in range(p):
    for i in range(n):
        qc.rzz(2 * gammas[layer], i, (i + 1) % n)
    for i in range(n):
        qc.rx(2 * betas[layer], i)
qc.measure_all()
