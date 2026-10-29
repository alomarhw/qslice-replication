from qiskit_ibm_runtime.fake_provider.fake_backend import FakeBackendV2
from qiskit_ibm_runtime import IBMBackend
from typing import Union

def two_qubit_conections(backend):
    if isinstance(backend, FakeBackendV2):
        return backend.coupling_map
    return backend.configuration().coupling_map
