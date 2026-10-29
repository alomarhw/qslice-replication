from qiskit.converters import circuit_to_gate

def circ_to_gate(circ):
    circ_gate = circuit_to_gate(circ)
    return circ_gate
