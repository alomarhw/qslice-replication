from qiskit.circuit.library import efficient_su2
from qiskit_ibm_transpiler.transpiler_service import TranspilerService

def ai_transpiling(num_qubits):
    circuit = efficient_su2(num_qubits, entanglement="circular", reps=1)
    transpiler_ai_true = TranspilerService(
        backend_name="ibm_brisbane",
        ai=True,
        optimization_level=3
    )

    transpiled_circuit = transpiler_ai_true.run(circuit)
    return transpiled_circuit
