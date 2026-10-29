from qiskit import QuantumCircuit

def bv_function(s):
    n = len(s)
    qc = QuantumCircuit(n + 1)
    for index, bit in enumerate(reversed(s)):
        if bit == "1":
            qc.cx(index, n)
    return qc
