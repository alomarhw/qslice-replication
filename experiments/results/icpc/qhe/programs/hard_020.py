from qiskit import QuantumCircuit
from qiskit_ibm_runtime.fake_provider import FakePerth
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

def transpile_ghz_customlayout():
    backend = FakePerth()
    ghz = QuantumCircuit(3)
    ghz.h(0)
    ghz.cx(0, [1, 2])
    ghz.barrier()
    pass_manager = generate_preset_pass_manager(optimization_level=1, backend=backend, initial_layout=[2, 4, 6])
    return pass_manager.run(ghz)
