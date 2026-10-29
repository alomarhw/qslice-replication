from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

def simons_algorithm(s):
    n = len(s)
    s = s[::-1]
    q_reg1 = QuantumRegister(n,"reg1")
    q_reg2 = QuantumRegister(n,"reg2")
    c_reg = ClassicalRegister(n, "c")
    circuit = QuantumCircuit (q_reg1, q_reg2, c_reg)
    circuit.h(q_reg1)
    circuit.barrier()
    circuit.cx(q_reg1, q_reg2)
    if "1" in s:
        i = s.find("1")
        for j in range(n):
            if s[j] == "1":
                circuit.cx(i, q_reg2[j])
    circuit.barrier()
    circuit.h(q_reg1)
    circuit.measure(q_reg1, c_reg)
    return circuit
