from qiskit.circuit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit.classical import expr
def conditional_quantum_circuit():
    """ Create a quantum circuit with 4 qubits and 4 classical bits. Apply Hadamard gates to the first three qubits, measure them, and apply an X gate to the fourth qubit inside a single conditional block whose condition is the XOR of the three measured bits. Finally, measure the fourth qubit. Use a single classical register named `c` holding all four classical bits, with qubit i measured into bit i.
    """
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
