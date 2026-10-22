"""PROTOCOL_ICPC.md section 3.5: before the corpus-L run, the oracle with the qubit limit raised to 20
(branch limit 64 above 16 qubits) must agree with Statevector + partial_trace to 1e-12 on random
unitary circuits of 17-20 qubits. Writes results/icpc/corpus_l/oracle_check.json.
Usage (from experiments/): python tests/test_oracle_corpus_l.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from qiskit.circuit.random import random_circuit
from qiskit.quantum_info import Statevector, partial_trace

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from icpc import oracle_icpc as oi  # noqa: E402

rows, worst = [], 0.0
for n in (17, 18, 19, 20):
    for seed in range(3):
        qc = random_circuit(n, depth=6, max_operands=2, seed=1000 * n + seed)
        got = oi.reduced_states(qc, range(n), max_qubits=20)
        sv = Statevector(qc)
        err = max(float(np.max(np.abs(np.asarray(partial_trace(sv, [k for k in range(n) if k != q]).data) - got[q])))
                  for q in range(n))
        worst = max(worst, err)
        rows.append({"n": n, "seed": seed, "max_abs_error": err})
        print(f"n={n} seed={seed} max|err|={err:.2e}", flush=True)
ok = worst <= 1e-12
out = HERE / "results" / "icpc" / "corpus_l" / "oracle_check.json"
out.write_text(json.dumps({"tolerance": 1e-12, "worst": worst, "pass": ok, "cases": rows}, indent=1))
print("PASS" if ok else "FAIL", f"worst {worst:.2e}")
sys.exit(0 if ok else 1)
