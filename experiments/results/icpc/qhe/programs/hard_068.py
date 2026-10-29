from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import Sampler
from numpy import pi

def zeno_elitzur_vaidman_bomb_tester(bomb_live):
    live_predictions = dud_predictions = detonations = 0
    shots = 1024
    cycles = 25
    e = pi/cycles
    measurements = cycles + 1 if bomb_live else 1
    circuit = QuantumCircuit(1, measurements)
    for i in range(cycles):
        circuit.ry(e, 0)
        if bomb_live:
            circuit.measure(0, i)
    circuit.measure(0, measurements - 1)
    backend = AerSimulator()
    sampler = Sampler(mode=backend)
    job = sampler.run([circuit],shots=shots).result()
    counts= job[0].data.c.get_counts()
    if bomb_live:
        for key, value in counts.items():
            if key[0] == '1':
                detonations += value
            elif '1' in key[1:]:
                dud_predictions += value
            else:
                live_predictions += value
    else:
        live_predictions = counts['0'] if '0' in counts else 0
        dud_predictions = counts['1']
        detonations = 0
    return (live_predictions/shots, dud_predictions/shots, detonations/shots)
