from qiskit_ibm_runtime import QiskitRuntimeService

def backend_info():
    service = QiskitRuntimeService()
    backends = service.backends(simulator=False, operational=True, min_num_qubits=20)
    backend_info = []
    for b in backends:
        backend_info.append({"backend_name": b.name, "num_qubits": b.num_qubits, "instructions": b.operation_names})        
    sorted_backend_info = sorted(backend_info, key=lambda x: x["backend_name"])
    return sorted_backend_info
