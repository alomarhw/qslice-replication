from qiskit import QuantumCircuit
from qiskit import qpy

def create_binary_serialization():
    qc = QuantumCircuit(2, name='Bell', metadata={'test': True})
    qc.h(0)
    qc.cx(0, 1)
    with open('bell.qpy', 'wb') as fd:
        qpy.dump(qc, fd)
