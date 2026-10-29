from qiskit import QuantumCircuit
from numpy import pi

def for_loop_circuit(qc, n):
    with qc.for_loop(range(n)) as i:
        qc.ry(pi/n*i, 0)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure(0, 0)
        with qc.if_test((qc.clbits[0], 1)):
            qc.break_loop()
    return qc
