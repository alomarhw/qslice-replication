from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import Sampler
from qiskit.primitives.containers.primitive_result import PrimitiveResult

def bv_algorithm(s):
    n = len(s)
    qc = QuantumCircuit(n + 1)
    qc.x(n)
    qc.h(n)
    for index in range(n):
        qc.h(index)
    for index, bit in enumerate(reversed(s)):
        if bit == "1":
            qc.cx(index, len(s))
    for index in range(n):
        qc.h(index)
    qc.measure_all()
    backend = AerSimulator()
    sampler = Sampler(mode=backend)
    result= sampler.run([qc], shots=1).result()
    bitstrings = result[0].data.meas.get_bitstrings()
    return [bitstrings, result]
