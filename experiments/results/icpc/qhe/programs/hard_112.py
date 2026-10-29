from qiskit.quantum_info import Operator
from qiskit.circuit.library import PauliEvolutionGate
from qiskit.synthesis import LieTrotter
from qiskit import QuantumCircuit
from qiskit.quantum_info import Pauli, SparsePauliOp

def create_product_formula_circuit(pauli_strings, times, reps):
    qc = QuantumCircuit(len(pauli_strings[0]))
    synthesizer = LieTrotter(reps=reps)
    for pauli_string, time in zip(pauli_strings, times):
        pauli = Pauli(pauli_string)
        hamiltonian = SparsePauliOp(pauli)
        evolution_gate = PauliEvolutionGate(hamiltonian, time)
        synthesized_circuit = synthesizer.synthesize(evolution_gate)
        qc.append(synthesized_circuit.to_gate(), range(len(pauli_string)))
    return qc
