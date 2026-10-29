from qiskit.transpiler.passes import SolovayKitaev
from qiskit.transpiler import PassManager
from qiskit.circuit import QuantumCircuit

def sol_kit_decomp(circuit):
    pm = PassManager([SolovayKitaev()])
    circ_dec = pm.run(circuit)
    return circ_dec
