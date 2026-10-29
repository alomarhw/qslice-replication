from qiskit_ibm_runtime import fake_provider
import inspect

def backend_info(backend_name):
    # Find the backend class by searching through all fake backends
    backend_class = None
    for name, obj in inspect.getmembers(fake_provider):
        if inspect.isclass(obj) and name.startswith('Fake'):
            try:
                temp_backend = obj()
                if temp_backend.name == backend_name:
                    backend_class = obj
                    break
            except:
                pass
    
    if backend_class is None:
        raise ValueError(f"Backend '{backend_name}' not found")
    
    backend = backend_class()
    config = backend.configuration()
    dict_result = {"num_qubits": config.num_qubits, "coupling_map": config.coupling_map, "supported_instructions": config.supported_instructions}

    return dict_result
