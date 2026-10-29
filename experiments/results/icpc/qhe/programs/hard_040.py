from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import Sampler
from qiskit_ibm_runtime.options import SamplerOptions

def init_random_3qubit(desired_vector):
    qc = QuantumCircuit(3)
    qc.initialize(desired_vector, range(3))
    qc.measure_all()
    backend = AerSimulator()
    options = SamplerOptions()
    options.simulator.seed_simulator=42
    sampler = Sampler(mode=backend,options=options)
    result = sampler.run([qc]).result()
    return result[0].data.meas.get_counts()
