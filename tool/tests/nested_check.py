"""Nested conditions: on the repetition code (tool/tests/big/repetition_code.py, safe to run), for every qubit,
how often the circuit's light cone (experiments/icpc/b_reference.py) and the tool's slice are wrong under random
product inputs, judged by exact simulation. Writes experiments/results/icpc/tool_acceptance/nested_check.json.
Usage (workspace root): python -m tool.tests.nested_check"""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, "experiments")
from tool.interp import trace_file
from tool.slicer import wire_slice
from tool.tests.check_trace import built, flat

P, DRAWS, SEED = "tool/tests/big/repetition_code.py", 30, 5


def main():
    from icpc import b_reference as oi
    from icpc.b_reference import light_cone, materialise
    qc0 = built(P)
    qc = qc0.copy_empty_like()
    for i in qc0.data:
        if i.operation.name != "barrier":
            qc.append(i)
    pos = []
    for k, inst in enumerate(qc.data):
        sub = qc.copy_empty_like(); sub.append(inst); pos += [k] * len(flat(sub))
    c = trace_file(P).main_circuit()
    assert len(c.ops) == len(pos)
    rng = np.random.default_rng(SEED)
    out = []
    for t in range(qc.num_qubits):
        tool = {pos[k] for k in wire_slice(c, [t], keep_terminal=True).ops}
        study = light_cone(qc, t)
        ws = wt = 0
        for _ in range(DRAWS):
            prep = oi.haar_product_input(qc.num_qubits, rng)
            base = oi.reduced_states(oi.with_input(qc, prep), [t])[t]
            ws += oi.fidelity(base, oi.reduced_states(oi.with_input(materialise(qc, study), prep), [t])[t]) < 1 - oi.FIDELITY_EPS
            wt += oi.fidelity(base, oi.reduced_states(oi.with_input(materialise(qc, tool), prep), [t])[t]) < 1 - oi.FIDELITY_EPS
        out.append({"qubit": t, "study_wrong": int(ws), "tool_wrong": int(wt), "draws": DRAWS})
    res = {"program": P, "draws": DRAWS, "qubits": out,
           "study_wrong_max": max(r["study_wrong"] for r in out), "tool_wrong_total": sum(r["tool_wrong"] for r in out)}
    Path("experiments/results/icpc/tool_acceptance/nested_check.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "qubits"}))


if __name__ == "__main__":
    main()
