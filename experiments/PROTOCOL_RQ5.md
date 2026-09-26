# Pre-registered protocol, experiment 3: RQ5 scalability of the Sec. III implementation

This protocol extends `PROTOCOL.md`: same environment, same preparation, same corpus A. It was
committed together with `rq5_scalability/run.py` **before** the full run. Before freezing, only two
checks were made:
- that the structural selection reproduces the submitted Table VII rows;
- a plumbing call on one circuit per part, whose output was discarded.

The run is executed once, and all outputs are reported.

Why: the submitted RQ5 timed graph construction of the simplified implementation, not the method of
Sec. III. Reviewer B also asked for end-to-end runtime and peak memory including the
mutual-information pruning and verification.

## 5.1 Part S: structural scalability (replaces Table VII and Fig. 3)
- **Circuits:** the 1,124 circuits of the submitted Table VII, selected by the same rules as the
  submitted `scripts/scalability.py`:
  - corpora order;
  - files of at most 800 KB;
  - 2-200 qubits and at most 4000 operations;
  - 8 s parse timeout;
  - de-duplication by (name, qubits, operations);
  - sort by (qubits, operations).

  The selection is checked row by row against the submitted table. If it differs, the run stops.
- **Loading:** each circuit is loaded as written with `qasm2.load` and prepared as in `PROTOCOL.md`
  section 1.
- **Implementation:** the method prototype with the control-edge patch (primary configuration of
  experiment 2).
- **Measured per circuit, in a fresh process:**
  - QDG construction time, with data, control and entanglement edges;
  - edge counts by type;
  - time of the causal backward slice from qubit 0;
  - peak resident memory.

## 5.2 Part E: end-to-end cost (new; answers Reviewer B)
- **Circuits:** corpus A, the 158 circuits of experiment 2.
- **Measured per circuit, in a fresh process:**
  - QDG construction;
  - `entanglement_pruned_slice` for every qubit, i.e. causal cone, mutual-information nomination and
    exact verification: total time and slowest single criterion;
  - peak resident memory.

## 5.3 Limits and reporting
- **Limits:** 120 s wall time and 4 GiB resident memory per circuit. A process that exceeds either is
  killed, and the circuit is reported as *not completed* with the limit it hit. This is part of the
  result, not an exclusion.
- **Parallelism:** at most 4 circuits run concurrently. The machine, Python version and limits are
  recorded in `machine.json`.
- **Timings** are wall-clock. They are reported as measured on that machine, and are not expected to
  repeat exactly. Everything except the timing and memory columns is deterministic.
- **Reported summaries:**
  - completion rate;
  - median, 95th percentile and maximum build time;
  - edges per instruction;
  - median, 95th percentile and maximum end-to-end time;
  - peak memory.
