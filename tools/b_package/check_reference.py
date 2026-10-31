"""Workspace-only check (not shipped): experiments/icpc/b_reference.py against the study code it replaces for
Paper B (slicers/registry.py lc, yz and the LightCone wrapper; common.corpus.prepare; icpc/oracle_icpc reduced
states). Every circuit Paper B's numbers slice, every qubit. Usage (workspace root): python tools/b_package/check_reference.py
"""
import csv, glob, sys, json
from pathlib import Path
import numpy as np
sys.path[:0] = [".", "experiments"]
from icpc import b_reference as B

def circuits():
    from icpc.rq3_bugs4q import _load
    for b in csv.DictReader(open("experiments/results/icpc/source_map/bugs.csv")):
        stem = b["bug_id"].replace("/", "__")
        yield "bugs4q:" + stem, _load(stem, "buggy"), True
    from tool.tests.check_trace import built
    progs = sorted(Path("tool/tests/big").glob("*.py")) + sorted(Path("tool/tests/programs").glob("t0*.py")) + \
        sorted(p for p in Path("paper/figures/src/programs").glob("*.py")
               if p.name != "bv.py" and not p.name.startswith(("lintq_", "qchecker_")))
    for p in progs:
        qc = built(str(p)); nb = qc.copy_empty_like()
        for i in qc.data:
            if i.operation.name != "barrier":
                nb.append(i)
        yield "dev:" + p.name, nb, False
    from qiskit import qasm2
    qb = sorted(glob.glob("data/QASMBench-master/QASMBench-master/*/*/*.qasm"))
    for f in qb:
        try:
            qc = qasm2.load(f, custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
        except Exception:
            continue
        if qc.num_qubits <= 14 and len(qc.data) <= 3000:
            yield "qasmbench:" + Path(f).name, qc, False

def main():
    from slicers.registry import Slicers
    from common.corpus import prepare
    from icpc import oracle_icpc as oi
    n = bad = 0
    out = {"circuits": 0, "qubits": 0, "lc_diff": 0, "yz_diff": 0, "lcq_diff": 0, "prepare_diff": 0, "states_diff": 0}
    rng = np.random.default_rng(1)
    for name, qc, is_prepared in circuits():
        out["circuits"] += 1
        p_old, p_new = prepare(qc), B.prepare(qc)
        if [(i.operation.name, tuple(i.qubits)) for i in p_old.data] != [(i.operation.name, tuple(i.qubits)) for i in p_new.data]:
            out["prepare_diff"] += 1; print("PREPARE", name)
        s = Slicers(qc, name); g = B.QPDG(qc)
        sp = Slicers.__new__(Slicers); sp.qc = p_old
        for t in range(qc.num_qubits):
            out["qubits"] += 1
            if s.lc(t) != B.light_cone(qc, t):
                out["lc_diff"] += 1; print("LC", name, t)
            if s.yz(t) != g.slice(t):
                out["yz_diff"] += 1; print("YZ", name, t)
            try:
                a = sp._lightcone(t, ("Z",))
            except Exception as e:
                a = type(e).__name__
            try:
                b = B.lightcone_pass(p_new, t, ("Z",))
            except Exception as e:
                b = "NotApplicable" if isinstance(e, B.NotApplicable) else type(e).__name__
            if a != b:
                out["lcq_diff"] += 1; print("LCQ", name, t, str(a)[:40], str(b)[:40])
        if qc.num_qubits <= 10:
            try:
                prep = oi.haar_product_input(qc.num_qubits, np.random.default_rng(7))
                ro = oi.reduced_states(oi.with_input(p_old, prep), range(qc.num_qubits))
                rn = B.reduced_states(B.with_input(p_new, prep), range(qc.num_qubits))
                if any(not np.allclose(ro[q], rn[q], atol=1e-9) for q in ro):
                    out["states_diff"] += 1; print("STATES", name)
            except Exception as e:
                pass
    print(json.dumps(out))

if __name__ == "__main__":
    main()
