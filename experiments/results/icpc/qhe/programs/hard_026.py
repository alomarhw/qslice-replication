from qiskit.dagcircuit import DAGCircuit
from qiskit import QuantumRegister, ClassicalRegister, QuantumCircuit
from qiskit.converters import circuit_to_dag

def bell_dag():
    q = QuantumRegister(3, 'q')
    c = ClassicalRegister(3, 'c')
    circ = QuantumCircuit(q, c)
    circ.h(q[0])
    circ.cx(q[0], q[1])
    circ.measure(q[0], c[0])
    dag = circuit_to_dag(circ)
    return dag
