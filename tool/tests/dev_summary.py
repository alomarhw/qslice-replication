"""Development checks of the tool, recorded as a result: for each program of our own (safe to run), whether the
static trace equals the circuit Qiskit builds, and whether every qubit's slice equals S-lc on that circuit.
Usage (workspace root): python -m tool.tests.dev_summary  -> experiments/results/icpc/tool_acceptance/dev_checks.json"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, "experiments")
from tool.interp import trace_file
from tool.slicer import wire_slice
from tool.tests.check_trace import built, flat

PROGS = sorted(Path("tool/tests/big").glob("*.py")) + sorted(Path("tool/tests/programs").glob("t0*.py")) + \
        sorted(Path("paper/figures/src/programs").glob("*.py"))


def main():
    from slicers.registry import Slicers
    out = []
    for p in PROGS:
        c = trace_file(p).main_circuit()
        qc = built(str(p))
        mine = [(o.name, tuple(next(iter(s)) for s in o.qubits)) for o in c.ops]
        trace_eq = mine == flat(qc)
        nb = qc.copy_empty_like()
        for inst in qc.data:
            if inst.operation.name != "barrier":
                nb.append(inst)
        s = Slicers(nb, str(p))
        diff_q = []
        for q in range(nb.num_qubits):
            a = Counter((c.ops[k].name, tuple(sorted(next(iter(x)) for x in c.ops[k].qubits))) for k in wire_slice(c, [q], keep_terminal=True).ops)
            b = Counter()
            for k in s.lc(q):
                sub = nb.copy_empty_like(); sub.append(nb.data[k])
                for name, qs in flat(sub):
                    b[(name, tuple(sorted(qs)))] += 1
            if a != b:
                diff_q.append(q)
        nested = any(i.operation.name == "if_else" and any(j.operation.name == "if_else" for j in i.operation.blocks[0].data) for i in qc.data)
        out.append({"program": str(p), "ops": len(c.ops), "qubits": nb.num_qubits, "trace_equal": trace_eq,
                    "slices_equal": not diff_q, "differing_qubits": diff_q, "nested_conditions": nested})
    Path("experiments/results/icpc/tool_acceptance").mkdir(parents=True, exist_ok=True)
    Path("experiments/results/icpc/tool_acceptance/dev_checks.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({"programs": len(out), "trace_equal": sum(r["trace_equal"] for r in out),
                      "slices_equal": sum(r["slices_equal"] for r in out), "max_ops": max(r["ops"] for r in out),
                      "differ_only_nested": all(r["nested_conditions"] for r in out if not r["slices_equal"])}))


if __name__ == "__main__":
    main()
