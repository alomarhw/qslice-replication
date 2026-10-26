"""On programs we may run: the tool's wire slice of every qubit, as (gate, qubits) operations, must equal the
study's circuit-level wire slicer (slicers/registry.py S-lc) on the circuit Qiskit builds.
Usage: python -m tool.tests.check_slice PROGRAM.py ..."""
import sys
sys.path.insert(0, "experiments")
from collections import Counter
from tool.interp import trace_file
from tool.slicer import wire_slice
from tool.tests.check_trace import built, flat


def main():
    from slicers.registry import Slicers
    bad = 0
    for p in sys.argv[1:]:
        t = trace_file(p)
        c = t.main_circuit()
        qc = built(p)
        nb = qc.copy_empty_like()  # the study's loader drops barriers before slicing (experiments/common/corpus.py)
        for inst in qc.data:
            if inst.operation.name != "barrier":
                nb.append(inst)
        qc = nb
        s = Slicers(qc, p)
        for q in range(qc.num_qubits):
            mine = Counter((c.ops[k].name, tuple(sorted(next(iter(x)) for x in c.ops[k].qubits))) for k in wire_slice(c, [q], keep_terminal=True).ops)
            ref = Counter()
            for k in s.lc(q):
                sub = qc.copy_empty_like()
                sub.append(qc.data[k])
                for name, qs in flat(sub):
                    ref[(name, tuple(sorted(qs)))] += 1
            if mine != ref:
                bad += 1
                print(f"DIFF {p} q{q}: tool-only {mine - ref}, study-only {ref - mine}")
        print(f"done {p}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
