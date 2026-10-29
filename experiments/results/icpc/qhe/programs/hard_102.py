from qiskit.circuit import QuantumCircuit
from qiskit_ibm_runtime.fake_provider import FakeKyoto, FakeKyiv, FakeAuckland
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

def backend_with_least_instructions():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    backends = [FakeKyiv(), FakeKyoto(), FakeAuckland()]
    qc_isa_num_intruc = {}
    for backend in backends:
        pm = generate_preset_pass_manager(optimization_level=0, backend=backend)
        qc_isa_num_intruc[backend.name] = len(pm.run(qc).data)
    return min(qc_isa_num_intruc, key=qc_isa_num_intruc.get)
