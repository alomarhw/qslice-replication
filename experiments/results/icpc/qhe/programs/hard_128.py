from qiskit.circuit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit.classical import expr

def conditional_quantum_circuit():
    qr = QuantumRegister(4, "q")
    cr = ClassicalRegister(4, "c")
    circ = QuantumCircuit(qr, cr)

    circ.h(qr[0:3])
    circ.measure(qr[0:3], cr[0:3])

    _condition = expr.bit_xor(expr.bit_xor(cr[0], cr[1]), cr[2])
    with circ.if_test(_condition):
        circ.x(qr[3])

    circ.measure(qr[3], cr[3])

    return circ
