from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import Sampler
from qiskit.circuit.library import XOR

def xor_gate(a, b):
    circuit = XOR(8, a).compose(XOR(8, b))
    circuit.measure_all()
    backend = AerSimulator()
    sampler = Sampler(mode=backend)
    result = sampler.run([circuit.decompose()]).result()
    return result[0].data.meas.get_counts()
