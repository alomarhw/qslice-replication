from qiskit import QuantumCircuit
def inefficientNOT(inefficiencies: int, inp: str):
    qc = QuantumCircuit(1, 1)
    qc.reset(0)
    if inp == '1':
        qc.x(0)
    qc.barrier()
    for i in range(inefficiencies):
        print(i + 1, " x gates added")
        qc.x(0)
    qc.barrier()
    qc.measure(0, 0)
    trial = qc.measure(0, 0)  # Bug
    return qc
