# Pre-registered protocol for the corrected experiments

This protocol was written, and committed together with all code, **before** any full run. Each full
run is executed once, and whatever it produces is reported. During development, only debugging runs
were made: at most 3 circuits of corpus A, plus `dqc_teleportation` from corpus B. All their outputs
were deleted. Any later deviation from this protocol will be listed in `DEVIATIONS.md`, with its
reason.

Why: two parts of the submitted evaluation cannot stand.
- Table VI's driver and circuit list were not preserved.
- The code that produced Tables III-V is not the method described in Sec. III.

This protocol replaces both with measurements whose every choice is fixed in advance.

## 1. Common to both experiments

**Environment.** Python 3.12, qiskit 2.3.0, numpy 1.26.4, scipy 1.13.1, networkx 3.4.2,
pandas 2.2.2, matplotlib 3.9.1. These are the versions pinned by the four-edge implementation and by
the method prototype.

**Corpus A (`common/corpus.py`).** The 161 circuits of the paper's RQ1-RQ3, selected by the
unchanged evaluation loader (`load_corpora`: at most 14 qubits and 220 operations, at most 80 per
corpus, smallest first). The loader supplies only the file list. Each file is then loaded as written
with `qiskit.qasm2.load` (legacy custom instructions), so mid-circuit measurement, reset and classical
feedback are kept. The submitted evaluation silently dropped these operations.

**Preparation, applied identically to every circuit before any slicer sees it:**
1. drop barriers;
2. drop terminal measurements. A measurement is terminal when no later instruction acts on its
   qubit and its bit is never read by a later condition. They are dropped because the criterion is
   the reduced state before readout;
3. decompose gates acting on more than 8 qubits, repeating until none remain.

**Criteria.** Every qubit of every circuit, as in the paper's RQ1.

**Slice materialisation.** A slice is a set of instruction positions. It is materialised as the
original instructions at those positions, in order, on the original registers (`common/evaluate.py`,
`materialise`). All slicers are judged through this one function.

**Oracle (`common/oracle.py`).** Exact simulation as an ensemble of pure-state branches:
- each mid-circuit measurement or reset splits branches, with exact probabilities;
- `if_else` is resolved per branch;
- a terminal measurement dephases its qubit.

The oracle returns the exact 2x2 reduced density matrix of each qubit at the end of the circuit.
- A slice is **sound** iff the Uhlmann fidelity between the criterion's reduced state in the slice
  and in the full circuit is **>= 1 - 1e-6**. This is the threshold stated in the paper (Table I).
- No sampling, no calibration, no fallback values.
- A circuit whose oracle needs more than 4096 branches, or hits an unsupported instruction, is
  **excluded and listed** in `excluded.json`.

Checks, in `tests/test_oracle.py` and run before this protocol was frozen:
- on 60 random unitary circuits the oracle agrees with Qiskit `Statevector` + `partial_trace` to
  2e-16;
- teleportation with feedback reproduces the input state exactly;
- reset, mid-circuit measurement and terminal measurement give their analytic results;
- on the 143 unitary circuits of corpora A and B it agrees with `Statevector` to 4e-16.

One circuit, `veriqbench/dynamic/qft/dqc_qft_14.qasm`, exceeds 4096 branches and is excluded.
`qasmbench/small/vqe_uccsd_n4.qasm` fails to parse in `qasm2.load` and is excluded.

**Statistics (`common/evaluate.py`).**
- Paired binary outcomes: exact two-sided McNemar test (binomial on discordant pairs).
- Paired sizes: two-sided Wilcoxon signed-rank test, plus mean difference with a bootstrap 95% CI
  (10,000 resamples, seed 42) and the rank-biserial correlation.
- No multiple-comparison correction beyond reporting all tests. p-values are reported, not
  thresholded.

## 2. Experiment 1: RQ4 edge-type ablation (replaces Table VI and Fig. 2)

**Slicer.** The four-edge implementation (`reported_results/rq4_ablation/src`), unchanged:
`qdg_from_circuit`, `slice_from_qdg` with the edge sets in `VARIANT_EDGE_TYPES`. The variants are
QSlice-full, QDG-no-ED, QDG-no-MD, QDG-no-UED and QDG-no-CD, plus Classical PDG and Causal-cone for
context.

**Corpus.**
- Corpus A.
- **Corpus B:** every `veriqbench/dynamic/**.qasm` circuit that has at most 14 qubits and at most 220
  instructions after preparation, and is not already in A. That is 20 circuits.
- Results are reported for A, B, A+B, and for the dynamic circuits (measurement, reset or feedback
  after preparation) within A+B.

**Metrics.**
- SVR(variant) = fraction of (circuit, criterion) pairs whose slice is unsound.
- **Primary: dSVR(edge type) = SVR(variant without it) - SVR(QSlice-full), over the pairs of A+B.**
- Secondary: the same per circuit, where a circuit violates if any criterion does; the same within
  each scope; and an exact McNemar test of each ablated variant against QSlice-full over pairs.

**Driver.** `rq4_ablation_rerun/run.py`. Outputs: `records.csv` (every pair and variant),
`TAB_ablation_rerun.csv`, `tests.json`, `excluded.json`.

## 3. Experiment 2: RQ1-RQ3 with the method described in Sec. III (replaces Tables III-V)

**3.1 Slicers.** From the method prototype (`described_method/qdg.py`), with the QDG built with data,
control and entanglement edges:
- QPDG = `entanglement_pruned_slice(t)`, the Sec. III method: causal cone, mutual-information pruning
  at `sep_eps = 1e-9`, trace-distance verification, and fallback to the causal cone on non-unitary
  circuits;
- naive = `naive_classical_backward_slice(t)`;
- causal = the QDG without entanglement edges, `backward_slice(t)`.

Forward slices: `forward_slice`, `naive_classical_forward_slice`, and the causal `forward_slice`.

**3.2 Control-edge patch.** Debugging on `dqc_teleportation` showed that the prototype never builds
the measurement -> conditioned-operation CONTROL edges that Sec. III describes. The cause is two
defects in `_add_control_edges` under qiskit 2.3.0, documented in `method_eval/control_fix.py`. As a
result its causal cone, and hence the QPDG slice, omits the measurements that a correction depends on.
- **Primary run:** the prototype with the minimal patch in `method_eval/control_fix.py`, a subclass
  that replaces only `_add_control_edges`: each conditioned operation gets an edge from the most
  recent earlier measurement of every bit its condition reads.
- **Secondary run:** the prototype unchanged.

Both are reported.

**3.3 Corpus and criteria.** Corpus A, every qubit.

**3.4 Metrics, per (circuit, criterion) pair.**
- **RQ1:** invalid-slice rate (unsound) and mean criterion fidelity, per slicer. Exact McNemar test,
  QPDG vs naive.
- **RQ2:** mean slice size (instructions in the slice / instructions in the prepared circuit). The
  QPDG vs causal comparison is restricted to pairs sound under both: Wilcoxon signed-rank, with mean
  difference, bootstrap CI and the number of pairs where QPDG is strictly smaller.
- **RQ3:**
  - Ground truth: the qubits whose exact reduced state changes (trace distance > 1e-9) when X is
    applied to the criterion at the input.
  - Covered qubits: those acted on by the forward slice, plus the criterion.
  - Completeness = |truth ∩ covered| / |truth|, or 1 when truth is empty. Complete = truth ⊆ covered.
  - The slice is **not** intersected with the truth. Mean completeness and complete-rate per slicer;
    exact McNemar test on complete flags, QPDG vs naive.
- Per-corpus breakdown of all of the above.

**Driver.** `method_eval/run.py --variant control-fixed` (primary) and `--variant unchanged`
(secondary). Outputs: `slice_records.csv`, `forward_records.csv`, `TAB1_method.csv`,
`TAB_per_corpus_method.csv`, `tests.json`, `excluded.json`.

## 4. Reporting commitments

- Every number in a corrected table comes from these outputs. Tables that change are replaced, not
  merged with old values.
- The paper states that the submitted Table VI could not be reproduced and that Tables III-V were
  produced by a simplified implementation. The corrected tables are identified as such.
- Results are reported whatever their direction, including if the QPDG does not beat the baselines,
  or if an edge type turns out not to matter.
