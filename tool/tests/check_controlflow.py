"""Soundness check of srcSlice-Q's slices of programs with in-circuit control flow (Deviation I-26).

For each of our programs in tool/tests/controlflow/ (safe to run) and each qubit q, the slice is applied to the
source as a developer would apply it: every line that emits an operation and is not in q's slice becomes `pass`.
Both programs are run to build their circuits, and an exact simulator that branches over measurement outcomes gives
q's reduced density matrix, at |0...0> and at seeded random product inputs. The slice is sound for q when the
fidelity is at least 1 - 1e-6 at every input. Measurements that nothing later depends on (tool.slicer.terminal) are
removed from both programs, since the criterion is the state before them. The real programs of the LintQ corpus and
Qiskit HumanEval that use these constructs are traced statically and never executed.
Usage (workspace root): python -m tool.tests.check_controlflow [--data-root DIR]
  -> experiments/results/icpc/controlflow/{check.csv, real.csv, summary.json}
"""
import argparse
import csv
import json
import runpy
import sys
import tempfile
from pathlib import Path

import numpy as np
from qiskit.circuit import ClassicalRegister, Clbit
from qiskit.circuit.controlflow import CASE_DEFAULT
from qiskit.quantum_info import DensityMatrix, Operator, partial_trace, state_fidelity

from tool import srcml as X
from tool.interp import Interpreter
from tool.slicer import terminal, wire_slice

HERE = Path(__file__).resolve().parent / "controlflow"
OUT = Path("experiments/results/icpc/controlflow")
SEED, INPUTS, EPS, CUTOFF, MAX_ROUNDS = 20261028, 5, 1e-6, 1e-13, 2000
P0, P1 = np.diag([1, 0]).astype(complex), np.diag([0, 1]).astype(complex)
XM = np.array([[0, 1], [1, 0]], dtype=complex)


class Sim:
    """Exact simulation of a circuit with measurements, resets and control flow: a map from classical outcomes
    (a tuple of bits) to an unnormalised density matrix."""

    def __init__(self, qc, rho0):
        self.qc, self.nc = qc, qc.num_clbits
        self.state = {(0,) * self.nc: rho0}

    def bit(self, b, cmap):
        return cmap[b] if b in cmap else self.qc.find_bit(b).index

    def value(self, bits, target, cmap):
        if isinstance(target, Clbit):
            return bits[self.bit(target, cmap)]
        return sum(bits[self.bit(b, cmap)] << i for i, b in enumerate(target))

    def holds(self, bits, cond, cmap):
        target, val = cond
        return self.value(bits, target, cmap) == int(val)

    def run(self, block, qmap, cmap, state):
        for inst in block.data:
            op = inst.operation
            qs = [qmap[q] for q in inst.qubits]
            cs = {b: self.bit(b, cmap) for b in inst.clbits}
            name = op.name
            if name == "barrier":
                continue
            if name in ("if_else", "while_loop", "for_loop", "switch_case"):
                state = self.control(op, inst, qmap, cmap, state)
                continue
            new = {}
            for bits, rho in state.items():
                if name == "measure":
                    q, cb = qs[0], cs[inst.clbits[0]]
                    for v, P in ((0, P0), (1, P1)):
                        r = rho.evolve(Operator(P), [q])
                        if abs(r.trace()) > CUTOFF:
                            nb = list(bits)
                            nb[cb] = v
                            nb = tuple(nb)
                            new[nb] = new[nb] + r if nb in new else r
                elif name == "reset":
                    r = rho.evolve(Operator(P0), qs) + rho.evolve(Operator(P1), qs).evolve(Operator(XM), qs)
                    new[bits] = new[bits] + r if bits in new else r
                else:
                    r = rho.evolve(Operator(op), qs)
                    new[bits] = new[bits] + r if bits in new else r
            state = new
        return state

    def sub(self, body, inst, qmap, cmap):
        return ({bq: qmap[oq] for bq, oq in zip(body.qubits, inst.qubits)},
                {**cmap, **{bc: self.bit(oc, cmap) for bc, oc in zip(body.clbits, inst.clbits)}})

    def merge(self, *states):
        out = {}
        for s in states:
            for k, v in s.items():
                out[k] = out[k] + v if k in out else v
        return out

    def control(self, op, inst, qmap, cmap, state):
        name = op.name
        if name == "if_else":
            t, f = op.blocks[0], op.blocks[1] if len(op.blocks) > 1 else None
            yes = {k: v for k, v in state.items() if self.holds(k, op.condition, cmap)}
            no = {k: v for k, v in state.items() if k not in yes}
            yes = self.run(t, *self.sub(t, inst, qmap, cmap), yes)
            if f is not None:
                no = self.run(f, *self.sub(f, inst, qmap, cmap), no)
            return self.merge(yes, no)
        if name == "while_loop":
            body, done = op.blocks[0], {}
            for _ in range(MAX_ROUNDS):
                go = {k: v for k, v in state.items() if self.holds(k, op.condition, cmap)}
                done = self.merge(done, {k: v for k, v in state.items() if k not in go})
                if sum(abs(v.trace()) for v in go.values()) < CUTOFF:
                    return done
                state = self.run(body, *self.sub(body, inst, qmap, cmap), go)
            raise RuntimeError("while_loop did not terminate within the cutoff")
        if name == "for_loop":
            indexset, param, body = op.params
            for v in indexset:
                b = body.assign_parameters({param: v}) if param is not None else body
                state = self.run(b, *self.sub(b, inst, qmap, cmap), state)
            return state
        if name == "switch_case":
            out, rest = {}, dict(state)
            default = None
            for values, block in op.cases_specifier():
                if CASE_DEFAULT in values:
                    default = block
                    continue
                hit = {k: v for k, v in rest.items() if self.value(k, op.target, cmap) in values}
                rest = {k: v for k, v in rest.items() if k not in hit}
                out = self.merge(out, self.run(block, *self.sub(block, inst, qmap, cmap), hit))
            if default is not None:
                rest = self.run(default, *self.sub(default, inst, qmap, cmap), rest)
            return self.merge(out, rest)
        raise ValueError(name)

    def reduced(self, q):
        return sum(partial_trace(rho, [k for k in range(self.qc.num_qubits) if k != q]).data for rho in self.state.values())


def inputs(n, rng):
    out = [None]
    for _ in range(INPUTS):
        out.append([Operator(np.linalg.qr(rng.normal(size=(2, 2)) + 1j * rng.normal(size=(2, 2)))[0]) for _ in range(n)])
    return out


def reduced_state(qc, q, prep):
    rho = DensityMatrix.from_label("0" * qc.num_qubits)
    if prep is not None:
        for k, U in enumerate(prep):
            rho = rho.evolve(U, [k])
    s = Sim(qc, rho)
    s.state = s.run(qc, {b: i for i, b in enumerate(qc.qubits)}, {}, s.state)
    r = s.reduced(q)
    return r / np.trace(r)


def build(src: str):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(src)
    return runpy.run_path(fh.name)["qc"]


def blank(lines, drop):
    out = []
    for i, ln in enumerate(lines, 1):
        out.append((ln[: len(ln) - len(ln.lstrip())] + "pass") if i in drop else ln)
    return "\n".join(out) + "\n"


def check(path: Path, rng):
    tr = Interpreter(str(path), 60).run(X.parse_file(path))
    c = tr.main_circuit()
    op_lines = {o.line for o in c.ops}
    term = terminal(c)
    term_lines = {c.ops[k].line for k in term} - {o.line for k, o in enumerate(c.ops) if k not in term}
    src = path.read_text().splitlines()
    whole = build(blank(src, term_lines))
    rows = []
    for q in range(c.n("q")):
        s = wire_slice(c, [q])
        drop = (op_lines - s.quantum_lines) | term_lines
        sliced = build(blank(src, drop))
        worst = 1.0
        for prep in inputs(whole.num_qubits, rng):
            f = state_fidelity(DensityMatrix(reduced_state(whole, q, prep)), DensityMatrix(reduced_state(sliced, q, prep)), validate=False)
            worst = min(worst, float(f))
        rows.append({"program": path.name, "qubit": q, "slice_lines": len(s.quantum_lines), "op_lines": len(op_lines),
                     "deleted": len(drop - term_lines), "min_fidelity": round(worst, 9), "sound": int(worst >= 1 - EPS),
                     "notes": "|".join(m for _, m in tr.notes)})
    return rows


def real(data_root: Path):
    """The real programs that use in-circuit control flow, traced statically: read, never executed."""
    pats = (".while_loop(", ".for_loop(", ".switch(", ".if_test(")
    files = []
    lintq = data_root / "lintq" / "exp_v08" / "files_selected"
    if lintq.is_dir():
        files += [("lintq", p) for p in sorted(lintq.glob("*.py")) if any(x in p.read_text(errors="replace") for x in pats)]
    qhe = Path("experiments/results/icpc/qhe/programs")
    files += [("qhe", p) for p in sorted(qhe.glob("standard_*.py")) if any(x in p.read_text() for x in pats)]
    rows = []
    for corpus, p in files:
        try:
            tr = Interpreter(str(p), 60).run(X.parse_file(p))
            c = tr.main_circuit()
            rows.append({"corpus": corpus, "file": p.name, "ops": len(c.ops) if c else 0,
                         "conditioned_ops": sum(bool(o.cond) for o in c.ops) if c else 0,
                         "notes": "|".join(m for _, m in tr.notes)[:300], "error": "" if c and c.ops else "no circuit"})
        except Exception as exc:  # recorded as a result
            rows.append({"corpus": corpus, "file": p.name, "error": type(exc).__name__})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default="../qslice-icpc-data")
    a = ap.parse_args()
    rng = np.random.default_rng(SEED)
    rows = [r for p in sorted(HERE.glob("cf*.py")) for r in check(p, rng)]
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rs in (("check.csv", rows), ("real.csv", real(Path(a.data_root)))):
        keys = list(dict.fromkeys(k for r in rs for k in r))
        with open(OUT / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(rs)
        if name == "real.csv":
            rr = rs
    summ = {"programs": len({r["program"] for r in rows}), "qubits": len(rows), "inputs_per_qubit": INPUTS + 1,
            "sound": sum(r["sound"] for r in rows), "unsound": [r for r in rows if not r["sound"]],
            "mean_slice_share": round(sum(r["slice_lines"] / r["op_lines"] for r in rows) / len(rows), 4),
            "real_files": len(rr), "real_traced": sum(not r.get("error") for r in rr),
            "real_with_conditioned_ops": sum(int(r.get("conditioned_ops") or 0) > 0 for r in rr)}
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps({k: v for k, v in summ.items() if k != "unsound"}, indent=1))
    for r in summ["unsound"]:
        print("UNSOUND", r)
    return 0 if not summ["unsound"] else 1


if __name__ == "__main__":
    sys.exit(main())
