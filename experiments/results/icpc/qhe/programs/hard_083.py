from qiskit import QuantumCircuit
from qiskit.quantum_info import DensityMatrix, concurrence

def calculate_bell_state_properties():
    qc = QuantumCircuit(2, name='Bell')
    qc.h(0)
    qc.cx(0, 1)
    rho = DensityMatrix.from_instruction(qc)
    concur = concurrence(rho)
    return rho, concur
