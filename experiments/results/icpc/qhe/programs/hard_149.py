from statistics import mode
from qiskit.primitives import BitArray

def most_common_result(bits):
    return mode(bits.get_bitstrings())
