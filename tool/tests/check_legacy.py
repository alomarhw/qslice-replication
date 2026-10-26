"""Old-API program: compare the static trace with the expected trace written by hand from the source."""
from tool.interp import trace_file

EXPECTED = [("u3", [0], set(), 8), ("u1", [1], set(), 9), ("cnot", [0, 1], set(), 10), ("toffoli", [0, 1, 2], set(), 11),
            ("iden", [2], set(), 12), ("measure", [0], set(), 13), ("x", [2], {0, 1, 2}, 14), ("cu1", [1, 2], set(), 15),
            ("measure", [0], set(), 16), ("measure", [1], set(), 16), ("measure", [2], set(), 16)]
t = trace_file("tool/tests/programs/legacy_api.py")
c = t.main_circuit()
got = [(o.name, [next(iter(s)) for s in o.qubits], set(o.cond), o.line) for o in c.ops]
print("OK" if got == EXPECTED else f"DIFF\n got {got}\n exp {EXPECTED}", "| notes:", t.notes)
