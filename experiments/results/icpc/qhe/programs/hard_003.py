from qiskit import QuantumCircuit

def create_ghz(drawing=False):
    ghz = QuantumCircuit(3)
    ghz.h(0)
    ghz.cx(0, 1)
    ghz.cx(0, 2)
    ghz.measure_all()
    if drawing:
        return ghz, ghz.draw(output="mpl")
    return ghz