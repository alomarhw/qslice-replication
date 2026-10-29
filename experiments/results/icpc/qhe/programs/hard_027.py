from qiskit.dagcircuit import DAGCircuit
from qiskit.converters import circuit_to_dag
from qiskit.circuit.library import HGate
from qiskit import QuantumRegister, ClassicalRegister, QuantumCircuit

def apply_op_back():
    q = QuantumRegister(3, "q")
    c = ClassicalRegister(3, "c")
    circ = QuantumCircuit(q, c)
    circ.h(q[0])
    circ.cx(q[0], q[1])
    dag = circuit_to_dag(circ)
    dag.apply_operation_back(HGate(), qargs=[q[0]])
    return dag
