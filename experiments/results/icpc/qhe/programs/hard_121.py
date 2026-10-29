from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

def conditional_two_qubit_circuit():
    qr = QuantumRegister(1)
    cr = ClassicalRegister(2, 'c')
    qc = QuantumCircuit(qr, cr)

    qc.h(qr[0])
    qc.measure(qr[0], cr[0])
    with qc.if_test((cr[0], 1)):
        qc.x(qr[0])
    qc.measure(qr[0], cr[1])
    return qc
