"""An OpenQASM 3 corpus with known answers, for the OpenQASM 3 front end (groundwork).

Qiskit's exporter (qiskit.qasm3.dumps, installed with Qiskit) writes a circuit as OpenQASM 3. Exporting a circuit whose
contents we know gives a program and its answer:
  ours      our own programs (tool/tests/big, programs, controlflow), run as check_trace runs them, since they are
            ours; the answer is the trace tool.interp builds from the Python source, which the paper validates (RQ1),
            so the OpenQASM 3 front end must agree with the Qiskit front end on the same program; device loops,
            branches and switches are among them;
  corpus    every OpenQASM 2 file of the corpora under 1 MB that qiskit.qasm2.load reads, re-exported; the answer is
            the loaded circuit's operations (tool.tests.check_trace.flat).
-> data/openqasm3_roundtrip/{ours,corpus}/*.qasm with a .json answer beside each, and index.csv (source, out, status)
"""
import csv
import glob
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from qiskit import qasm2, qasm3  # noqa: E402

from tool.interp import trace_file  # noqa: E402
from tool.tests.check_trace import flat  # noqa: E402

OUT = ROOT / "data" / "openqasm3_roundtrip"
MAX_BYTES = 1_000_000


def size(qc) -> int:
    """Operations of a circuit, those inside control-flow blocks included."""
    return sum(1 + sum(size(b) for b in getattr(i.operation, "blocks", ())) for i in qc.data)


def program_circuit(path):
    """The circuit the program builds: of the circuits it creates, the largest counting its blocks. A control-flow
    block is a circuit too, and can hold more instructions than the circuit it belongs to (check_trace.built picks by
    instructions alone)."""
    from qiskit import QuantumCircuit
    made, orig = [], QuantumCircuit.__init__

    def init(self, *a, **k):
        orig(self, *a, **k)
        made.append(self)
    QuantumCircuit.__init__ = init
    try:
        import runpy
        runpy.run_path(path, run_name="__main__")
    finally:
        QuantumCircuit.__init__ = orig
    return max(made, key=size)


def op_row(op):
    return {"name": op.name, "qubits": [sorted(s) for s in op.qubits], "clbits": [sorted(s) for s in op.clbits],
            "cond": sorted(op.cond), "line": op.line, "iters": [list(i) for i in op.iters], "may": op.may}


def main():
    rows = []
    (OUT / "ours").mkdir(parents=True, exist_ok=True)
    (OUT / "corpus").mkdir(parents=True, exist_ok=True)
    for d in ("big", "programs", "controlflow"):
        for p in sorted((ROOT / "tool" / "tests" / d).glob("*.py")):
            out = OUT / "ours" / f"{d}__{p.stem}.qasm"
            try:
                qc = program_circuit(str(p))
                out.write_text(qasm3.dumps(qc))
                ans = {"source": str(p.relative_to(ROOT)), "kind": "qiskit-front-end trace",
                       "ops": [op_row(o) for o in trace_file(p).main_circuit().ops],
                       "flat": [list(x) for x in flat(qc)]}
                out.with_suffix(".json").write_text(json.dumps(ans))
                rows.append([str(p.relative_to(ROOT)), str(out.relative_to(ROOT)), "ok"])
            except Exception as exc:  # recorded, e.g. a construct the exporter cannot write
                rows.append([str(p.relative_to(ROOT)), "", f"{type(exc).__name__}: {str(exc)[:120]}"])
    files = sorted({os.path.realpath(f) for d in ("../qslice-icpc/data", "data") for f in glob.glob(str(ROOT / d) + "/**/*.qasm", recursive=True)
                    if os.path.isfile(f) and "openqasm3" not in f})
    for f in files:
        t = open(f, errors="replace").read()
        if len(t) > MAX_BYTES or re.search(r"OPENQASM\s+3", t) or re.search(r'include\s+"stdgates', t):
            continue
        rel = f.split("/data/")[-1]
        out = OUT / "corpus" / (re.sub(r"[^A-Za-z0-9_.-]", "_", rel)[:150])
        try:
            qc = qasm2.load(f, custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
            out.write_text(qasm3.dumps(qc))
            out.with_suffix(".json").write_text(json.dumps({"source": rel, "kind": "qiskit-loaded circuit",
                                                            "flat": [list(x) for x in flat(qc)]}))
            rows.append([rel, str(out.relative_to(ROOT)), "ok"])
        except Exception as exc:
            rows.append([rel, "", f"{type(exc).__name__}: {str(exc)[:120]}"])
    with open(OUT / "index.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "out", "status"])
        w.writerows(rows)
    ok = sum(r[2] == "ok" for r in rows)
    print(f"{ok} of {len(rows)} exported -> {OUT}")


if __name__ == "__main__":
    main()
