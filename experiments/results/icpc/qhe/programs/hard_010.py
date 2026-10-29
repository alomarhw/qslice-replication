from qiskit.circuit import QuantumCircuit
from qiskit.quantum_info.operators import Operator
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

def create_operator():
    XX = Operator([[0, 0, 0, 1], [0, 0, 1, 0], [0, 1, 0, 0], [1, 0, 0, 0]])
    circ = QuantumCircuit(2, 2)
    circ.append(XX, [0, 1])
    pass_manager = generate_preset_pass_manager(optimization_level=1, basis_gates=["u", "cx"])
    return pass_manager.run(circ)
