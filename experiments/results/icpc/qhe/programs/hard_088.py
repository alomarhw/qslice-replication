from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
from qiskit.circuit import IfElseOp

def create_conditional_circuit():
    qr = QuantumRegister(1, 'q')
    cr = ClassicalRegister(1, 'c')
    circuit = QuantumCircuit(qr, cr)
    circuit.h(qr[0])
    circuit.measure(qr[0], cr[0])
    true_body = QuantumCircuit(qr, cr)
    true_body.z(qr[0])
    false_body = QuantumCircuit(qr, cr)
    false_body.x(qr[0])
    if_else_gate = IfElseOp((cr, 1), true_body, false_body)
    circuit.append(if_else_gate, [qr[0]], [cr[0]])
    circuit.measure(qr[0], cr[0])
    return circuit
