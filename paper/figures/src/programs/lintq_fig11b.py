import numpy as np
from qiskit import QuantumCircuit
def test_linear_toffoli2(self):
    gate_x = np.array([[0, 1], [1, 0]])
    qc2 = QuantumCircuit(4)
    qc2.x(2)
    qc2.x(3)
    qc2.x(0)
    state1 = qclib.util.get_state(qc2)
    circ = QuantumCircuit(4)
    mc_gate(gate_x, circ, [3, 2, 1], 0)
    qc2.compose(circ, qc2.qubits)  # Bug
    state2 = qclib.util.get_state(qc2)
    self.assertTrue(np.allclose(state1, state2))
