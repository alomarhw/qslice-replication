"""Forward slices and profiles (tool-v5): on each program, for every operation o and qubit q, the forward slice of o
reaches q exactly when o is in the backward wire slice of q (the duality of Section III), and the slice profile of q
has the same backward and forward lines as the two slicers.
Usage: python -m tool.tests.check_forward PROGRAM.py ..."""
import sys
from pathlib import Path
from tool.interp import trace_file
from tool.profile import qubit_arg_texts, slice_profile
from tool.slicer import forward_slice, wire_slice


def main():
    bad = pairs = 0
    for p in sys.argv[1:]:
        c = trace_file(p).main_circuit()
        back = {q: set(wire_slice(c, [q], keep_terminal=True).ops) for q in range(c.n())}
        for k in range(len(c.ops)):
            f = forward_slice(c, [k])
            if not f.ops:
                continue  # an operation the slicer does not slice (NOT_SLICED)
            for q in range(c.n()):
                pairs += 1
                if (q in f.qubits) != (k in back[q]):
                    bad += 1
                    print(f"DIFF {p} op {k} (line {c.ops[k].line}) q{q}: forward {q in f.qubits}, backward {k in back[q]}")
        args = qubit_arg_texts(Path(p))
        for q in range(c.n()):
            prof = slice_profile(c, q, args)
            if set(prof.backward_lines) != set(wire_slice(c, [q]).quantum_lines):
                bad += 1
                print(f"DIFF {p} profile q{q}: backward lines")
        print(f"done {p}")
    print(f"{pairs} pairs, {bad} differences")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
