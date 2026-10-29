"""Negative controls for check_controlflow (Deviation I-26): the check must reject wrong slices.
(1) cf02, qubit 1, with the kickback CNOT of line 13 removed from its slice.
(2) The slices of the interpreter archived before I-26 (tag icpc-original-2026-10-28), which read in-circuit control
    flow as plain `with` blocks, through the same check. A sliced program whose while_loop no longer terminates is
    counted as a wrong slice.
Usage (workspace root): python -m tool.tests.check_controlflow_negative <archived workspace>
  -> experiments/results/icpc/controlflow/negative.json
"""
import json
import sys
from pathlib import Path

import numpy as np
from qiskit.quantum_info import DensityMatrix, state_fidelity

import tool.tests.check_controlflow as C


def main():
    rng = np.random.default_rng(C.SEED)
    p = C.HERE / "cf02_while_kickback.py"
    src = p.read_text().splitlines()
    whole, bad = C.build(C.blank(src, set())), C.build(C.blank(src, {13}))
    f1 = min(float(state_fidelity(DensityMatrix(C.reduced_state(whole, 1, pr)), DensityMatrix(C.reduced_state(bad, 1, pr)),
                                  validate=False)) for pr in C.inputs(3, rng))
    sys.path.insert(0, sys.argv[1])
    for m in [k for k in list(sys.modules) if (k == "tool" or k.startswith("tool.")) and not k.startswith("tool.tests")]:
        del sys.modules[m]
    import tool.interp as I, tool.slicer as S, tool.srcml as X  # noqa: E401
    assert Path(I.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve())
    C.Interpreter, C.wire_slice, C.terminal, C.X = I.Interpreter, S.wire_slice, S.terminal, X
    per = {}
    for f in sorted(C.HERE.glob("cf*.py")):
        try:
            rs = C.check(f, np.random.default_rng(C.SEED))
            per[f.name] = {"qubits": len(rs), "unsound": [r["qubit"] for r in rs if not r["sound"]],
                           "min_fidelity": min(r["min_fidelity"] for r in rs)}
        except RuntimeError as exc:
            per[f.name] = {"nonterminating": str(exc)}
    out = {"kickback_cnot_removed_min_fidelity": round(f1, 6), "archived_interpreter": per,
           "archived_programs_wrong": sum(bool(v.get("unsound")) or "nonterminating" in v for v in per.values()),
           "programs": len(per)}
    (C.OUT / "negative.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
