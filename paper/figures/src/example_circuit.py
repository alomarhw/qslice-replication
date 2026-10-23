from qiskit import QuantumCircuit

qc = QuantumCircuit(3)
qc.ry(0.9, 2)      # o0
qc.x(1)            # o1
qc.h(1)            # o2
qc.h(0)            # o3
qc.cx(0, 1)        # o4  kickback onto q0
qc.h(0)            # o5
qc.cx(1, 2)        # o6  q1, q2 entangled
qc.z(1)            # o7
