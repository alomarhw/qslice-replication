"""Acceptance test of the OpenQASM 2 front end and the one-pass slice (Deviation I-22), recorded as a result.

On every corpus-A circuit (OpenQASM files, read and never executed):
  trace     the front end's operations equal the circuit qiskit.qasm2.load builds (gate names and qubits, barriers
            left out, if-blocks expanded), as check_trace compares a Qiskit program with the circuit it builds;
  slice     every qubit's QDG slice on the trace equals the study's circuit-level QDG slice (Slicers.lc) on that
            circuit, as dev_summary compares them;
  onepass   compact_all_qubits gives every qubit the same slice as compact_slice and wire_slice.
On the QASMBench small and medium circuits, onepass alone (no circuit-level reference is needed).
Usage (workspace root): python -m tool.tests.check_qasm  -> experiments/results/icpc/qasm_frontend/check.json
"""
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, "experiments")
from qiskit import qasm2  # noqa: E402

from tool import qasm, slicer  # noqa: E402
from tool.tests.check_trace import flat  # noqa: E402

DATA = Path("data")
OUT = Path("experiments/results/icpc/qasm_frontend")
SMALL_ONEPASS_MAX = 20_000  # operations: separate passes per qubit stay cheap


def onepass_ok(path):
    cc = qasm.compact(path)
    term = slicer.compact_terminal(cc)
    _, sl = slicer.compact_all_qubits(cc, term, members=True)
    return all(slicer.compact_slice(cc, [q], term) == sl[q] for q in range(cc.n_qubits)), len(cc), cc.n_qubits


def main():
    from slicers.registry import Slicers
    paths = sorted({r["path"] for r in csv.DictReader(open("experiments/results/icpc/rq1/pairs.csv"))})
    rows = []
    for rel in paths:
        p = DATA / rel
        c = qasm.read(p).main_circuit()
        raw = qasm2.load(str(p), custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
        mine = [(o.name, tuple(next(iter(s)) for s in o.qubits)) for o in c.ops if o.name != "barrier"]
        trace_eq = mine == flat(raw)
        nb = raw.copy_empty_like()
        for inst in raw.data:
            if inst.operation.name != "barrier":
                nb.append(inst)
        s = Slicers(nb, rel)
        diff = []
        for q in range(nb.num_qubits):
            a = Counter((c.ops[k].name, tuple(sorted(next(iter(x)) for x in c.ops[k].qubits)))
                        for k in slicer.wire_slice(c, [q], keep_terminal=True).ops)
            b = Counter()
            for k in s.lc(q):
                sub = nb.copy_empty_like()
                sub.append(nb.data[k])
                for name, qs in flat(sub):
                    b[(name, tuple(sorted(qs)))] += 1
            if a != b:
                diff.append(q)
        op_ok, n_ops, n_q = onepass_ok(p)
        op_ok = op_ok and all(sorted(slicer.wire_slice(c, [q]).ops) == slicer.compact_slice(qasm.compact(p), [q])
                              for q in range(n_q))
        rows.append({"path": rel, "ops": len(c.ops), "qubits": n_q, "trace_equal": trace_eq, "slice_diff_qubits": diff,
                     "onepass_equal": op_ok})
    qb = []
    for p in sorted(Path("data/QASMBench-master/QASMBench-master").glob("*/*/*.qasm")):
        if p.parts[-3] not in ("small", "medium"):
            continue
        t0 = time.perf_counter()
        try:
            cc = qasm.compact(p)
        except Exception as exc:  # recorded as a result
            qb.append({"path": str(p.relative_to(DATA)), "error": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        if len(cc) > SMALL_ONEPASS_MAX:
            continue
        ok, n_ops, n_q = onepass_ok(p)
        qb.append({"path": str(p.relative_to(DATA)), "ops": n_ops, "qubits": n_q, "onepass_equal": ok,
                   "seconds": round(time.perf_counter() - t0, 3)})
    summ = {"corpus_a_circuits": len(rows), "trace_equal": sum(r["trace_equal"] for r in rows),
            "slice_equal": sum(not r["slice_diff_qubits"] for r in rows),
            "onepass_equal": sum(r["onepass_equal"] for r in rows),
            "qasmbench_checked": sum("onepass_equal" in r for r in qb),
            "qasmbench_onepass_equal": sum(r.get("onepass_equal", False) for r in qb),
            "qasmbench_errors": [r for r in qb if "error" in r]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "check.json").write_text(json.dumps({"summary": summ, "corpus_a": rows, "qasmbench": qb}, indent=1) + "\n")
    print(json.dumps(summ, indent=1))
    bad = [r for r in rows if not (r["trace_equal"] and not r["slice_diff_qubits"] and r["onepass_equal"])]
    for r in bad[:10]:
        print("DIFF", r)
    return 1 if bad or summ["qasmbench_onepass_equal"] != summ["qasmbench_checked"] else 0


if __name__ == "__main__":
    sys.exit(main())
