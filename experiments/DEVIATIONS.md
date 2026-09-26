# Deviations from PROTOCOL.md

## Deviation 1: post-preparation size cap applied to corpus A (2026-09-25, before any result)

**What happened.** The first full run of experiment 1 (commit `90b2991`) was stopped after about 60
minutes, because two worker processes had exhausted memory (about 20 GB of swap). No output file had
been written, and no result of that run was seen.

**Cause.** Preparation step 3 decomposes gates wider than 8 qubits. For two corpus-A circuits this
turns one wide oracle gate into a very large circuit:
- `mqtbench/grover_n14.qasm`: 100 raw instructions, 366,658 after preparation;
- `mqtbench/grover_n10.qasm`: 38 raw instructions, 33,670 after preparation.

The four-edge implementation adds transitive entanglement edges between all pairs of gates on
entangled qubits, which is quadratic in the gate count, so slicing these circuits does not fit in
memory. Every other circuit has at most 129 instructions after preparation.

**Change.** Corpus B was already restricted to at most 220 instructions after preparation. The same
cap is now applied to corpus A, so circuits whose prepared form exceeds 220 instructions are excluded
and listed in `excluded.json`. This removes exactly the two circuits above. The rule was chosen from
circuit sizes alone, before any soundness outcome was observed, and it applies to both experiments.

Corpus A for both experiments is therefore 158 circuits: 161, minus `vqe_uccsd_n4` (parse failure),
minus these two.
