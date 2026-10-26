"""T1 on programs we may run: the static trace must equal the circuit Qiskit builds when the program runs.
Usage: python -m tool.tests.check_trace PROGRAM.py [PROGRAM.py ...]   (only for programs that are safe to run)"""
import runpy, sys
from qiskit import QuantumCircuit
from tool.interp import trace_file


def built(path):
    made = []
    orig = QuantumCircuit.__init__

    def init(self, *a, **k):
        orig(self, *a, **k)
        made.append(self)
    QuantumCircuit.__init__ = init
    try:
        runpy.run_path(path, run_name="__main__")
    finally:
        QuantumCircuit.__init__ = orig
    return max(made, key=lambda c: len(c.data))


def flat(qc, outer=None):
    """(gate, global qubits) in order, with if_else blocks expanded recursively (a block's qubits map to the outer
    instruction's qubits)."""
    out = []
    for inst in qc.data:
        op = inst.operation
        idx = [qc.find_bit(q).index for q in inst.qubits]
        idx = [outer[i] for i in idx] if outer is not None else idx
        if op.name == "if_else":
            out.extend(flat(op.blocks[0], idx))
            continue
        out.append((op.name, tuple(idx)))
    return [x for x in out if x[0] != "barrier"]


def main():
    bad = 0
    for p in sys.argv[1:]:
        t = trace_file(p)
        c = t.main_circuit()
        mine = [(o.name, tuple(next(iter(s)) if len(s) == 1 else None for s in o.qubits)) for o in c.ops]
        ref = flat(built(p))
        ok = mine == ref
        bad += not ok
        print(f"{'OK  ' if ok else 'DIFF'} {p}: static {len(mine)} ops, built {len(ref)} ops; notes {t.notes}")
        if not ok:
            for i, (a, b) in enumerate(zip(mine + [None] * 5, ref + [None] * 5)):
                if a != b:
                    print("   first difference at", i, a, b)
                    break
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
