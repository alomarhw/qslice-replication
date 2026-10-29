from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import Sampler

def random_coin_flip(samples):
    circuit = QuantumCircuit(1,1)
    circuit.h(0)
    circuit.measure_all()
    backend = AerSimulator()
    sampler = Sampler(mode=backend)
    result = sampler.run([circuit], shots=samples).result()
    counts = result[0].data.meas.get_counts()
    return {'Heads' : counts['0'], 'Tails': counts['1']}
