import numpy as np
from qiskit import QuantumCircuit

n_nodes = 10
edges = [(i, (i + 1) % n_nodes) for i in range(n_nodes)] + [(0, 5), (2, 7), (3, 8)]
p = 3
gammas = np.linspace(0.1, 0.9, p)
betas = np.linspace(0.8, 0.2, p)


def cost_layer(qc, gamma):
    for u, v in edges:
        qc.rzz(2 * gamma, u, v)


def mixer_layer(qc, beta):
    for v in range(n_nodes):
        qc.rx(2 * beta, v)


qc = QuantumCircuit(n_nodes)
qc.h(range(n_nodes))
for layer in range(p):
    cost_layer(qc, gammas[layer])
    mixer_layer(qc, betas[layer])
qc.measure_all()
