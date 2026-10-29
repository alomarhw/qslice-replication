from qiskit_ibm_runtime.fake_provider import FakeCairoV2
from qiskit_aer.noise import NoiseModel

def gen_noise_model():
    backend = FakeCairoV2()
    noise_model = NoiseModel.from_backend(backend)
    return noise_model
