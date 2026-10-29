from qiskit import QuantumCircuit
from qiskit.transpiler.passes import CollectLinearFunctions
from qiskit.transpiler import PassManager

def collect_linear_blocks_with_and_without_limit():
    qc = QuantumCircuit(5)
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.cx(2, 3)
    qc.cx(3, 4)
    pm_full = PassManager([CollectLinearFunctions()])
    full_block = pm_full.run(qc)
    pm_limited = PassManager([CollectLinearFunctions(max_block_width=3)])
    limited_block = pm_limited.run(qc)
    return full_block, limited_block
