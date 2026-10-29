from qiskit_ibm_runtime import QiskitRuntimeService

def find_highest_rz_error_rate(backend_name):
    service = QiskitRuntimeService(channel="ibm_quantum_platform")
    backend = service.backend(backend_name)
    backend_properties = backend.properties()

    try:
        rz_props = backend_properties.gate_property("rz")
    except:
        return None

    qubit_pair = max(rz_props, key=lambda x: rz_props[x]["gate_error"][0])
    max_rz_error = rz_props[qubit_pair]["gate_error"][0]
    return (qubit_pair, max_rz_error)
