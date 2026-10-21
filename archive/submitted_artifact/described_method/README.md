# described_method/ — prototype of the method in Sec. III

**This code implements Sec. III of the paper. It did NOT produce the submitted numbers (Tables III-V).**
It produced two sets of results:
- `beta_run/`: the run behind the **beta manuscript** (June 24 draft). The files are archived
  byte-identical, and this code regenerates them to within 1.3e-11.
- `../corrected_results/`: the pre-registered corrected experiment, whose results replace Tables III-V.

It is the prototype of the entanglement-aware backward slicer as described in Sec. III, preserved
byte-identical (dated June 28, 2026). The numbers in the paper were produced by the evaluation code in
`reported_results/rq1_rq3_rq5/`; see `PROVENANCE.md` for how the two differ.

What this prototype implements (`qdg.py`):

- `entanglement_pruned_slice(target, sep_eps=1e-9)`:
  1. starts from the causal cone: the backward slice over data and classical-control edges, with
     entanglement edges removed;
  2. falls back to that causal-cone slice, without pruning, for any non-unitary circuit
     (mid-circuit measurement, reset, or classical feedback);
  3. marks as prune candidates only operations that do **not** act on the criterion qubit
     (lines 521-523), so operations on the criterion qubit are never removed;
  4. flags a candidate when every qubit it acts on has quantum mutual information with the criterion
     qubit below `sep_eps` (von Neumann entropy of Qiskit reduced states);
  5. keeps a prune only if the criterion qubit's reduced state of the pruned circuit stays within trace
     distance `sep_eps` of the full circuit's.
- Edge types: data, classical control (`c_if` / `if_test`), and entanglement.
- Baselines: a classical def-use slicer (`naive_classical_backward_slice`,
  `naive_classical_forward_slice`) and the causal cone (entanglement edges removed).

What it is not: it has no measurement-collapse (MD) edge type, and it is not the four-edge taxonomy of
Table VI.

Known defect: under its pinned qiskit 2.3.0, `_add_control_edges` never builds the measurement ->
conditioned-operation CONTROL edges, because register conditions are not recognised. The corrected
experiment's primary run uses a minimal documented patch (`../corrected_results/method_eval/control_fix.py`),
and its secondary run uses this code unchanged.

Requirements: `requirements.txt` (Qiskit). `main.py` expects the corpus under `data/` as in the package
root.
