from qiskit import QuantumCircuit
from qiskit.primitives import StatevectorSampler

def circuit_to_bools(circuit):
    result = StatevectorSampler().run([circuit], shots=1).result()[0].data.meas.get_counts()
    measurement_int = int(list(result.keys())[0], 2)
    output = []
    for bit_index in range(circuit.num_clbits):
        # Use bit-masking to get bits from `int`
        bit = bool(2 ** (bit_index) & measurement_int)
        output.append(bit)
    return output
