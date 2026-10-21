# Provenance: what produced each result, and how this repository differs from the submitted artifact

This repository contains only:
- the implementations that exist;
- results produced by them under pre-registered protocols;
- a repaired mechanization.

Every result regenerates from `reproduce.sh`. The submitted artifact had four problems:
1. The method in Sec. III was not the code that produced Tables III-V.
2. Table VI's driver was lost.
3. Table V's QPDG value held by construction.
4. The Isabelle theory rested on unsound axioms.

Each of these is replaced here by a measurement or proof whose choices were fixed before the result
was known.

## Paper item -> source -> status

| Paper item | Produced by | Result files | Status |
|---|---|---|---|
| Tables III, IV, V (RQ1-RQ3) | `qslice/qdg.py` (Sec. III method), `experiments/method_eval/run.py`, exact oracle | `experiments/results/method_primary/` (secondary: `method_secondary/`) | pre-registered; regenerates byte for byte |
| Table VI, Fig. 2 (RQ4) | `fouredge/src`, `experiments/rq4_ablation_rerun/run.py` | `experiments/results/rq4_ablation/`, `figures/fig2_ablation_rerun.png` | pre-registered; regenerates byte for byte |
| Table VII, Fig. 3 (RQ5) | `qslice/qdg.py`, `experiments/rq5_scalability/run.py` | `experiments/results/rq5_scalability/`, `figures/fig3_scalability.png` | pre-registered; deterministic columns regenerate; timings are machine-dependent |
| Table VIII, Fig. 4 (RQ6) | `isabelle/QSliceSoundness.thy` | `figures/fig4_isabelle.png` | builds with no sorry and no axioms; scope in `isabelle/README.md` |
| Table IX, Fig. 5 (RQ7) | `hardware/run_hardware.py` (four-edge slices) on `ibm_cleveland`; `hardware/scripts/recompute_hardware_tvd.py` | `hardware/reported/`, `figures/fig5_hardware_tvd.png` | recomputed from captured jobs; same content |
| Fig. 1 | `fouredge/src` on teleportation | `figures/fig1_qpdg_teleportation.png` | edge set identical to the submitted figure |
| Beta manuscript (June 24 draft): 242 circuits, 1,356 slices | `qslice/qdg.py` with its June 28 driver `qslice/main.py` | `qslice/beta_run/` (archived) | regenerates to within 1.3e-11 (not byte-identical); not pre-registered; sampled targets, unitary circuits only |

## Headline results against the submitted values

| Claim | Submitted | This repository |
|---|---|---|
| QPDG invalid-slice rate (RQ1) | 0.000 | 0.000 (784 pairs) |
| Naive def-use invalid-slice rate (RQ1) | 0.429 | 0.276 |
| Slice size, QPDG vs causal cone (RQ2) | 0.433 vs 0.758 (43% smaller) | 0.540 vs 0.704 (23% smaller; 477 of 784 pairs strictly smaller) |
| Forward completeness, QPDG vs naive (RQ3) | 1.000 vs 0.702 (QPDG by construction) | 1.000 vs 0.988 (both measured against the exact influence set) |
| Ablation dSVR, ED / MD / UED / CD (RQ4) | 0.588 / 0.382 / 0.294 / 0.000 (34 circuits) | 0.535 / 0.129 / 0.128 / 0.043 (962 pairs); dynamic-circuit pairs 0.399 / 0.481 / 0.217 / 0.159 |
| Full four-edge slicer SVR | 0 | 0.0052 (5 pairs, all with mid-circuit measurement) |
| RQ5 structural | build < 1 s on 1,124 circuits (simplified implementation) | Sec. III implementation: 993 of 1,062 parsable circuits completed (69 reached 4 GiB; 62 not parsable by qiskit.qasm2); median build 28 ms, p95 9.5 s, max 20.8 s |
| RQ5 end to end | not measured | 157 of 158 circuits completed (grover_n8 reached 120 s); pruned slicing over all criteria: median 43 ms, p95 1.5 s, max 8.0 s; peak memory at most 214 MB |
| RQ6 | "7 obligations machine-checked" from unsound axioms | causal-cone soundness from two true locale assumptions; pruning covered by the runtime check |
| RQ7 | 16/18 circuits TVD < 0.05 | unchanged (same captured jobs) |

## What the submitted artifact contained, and why it is not at the top level
The submitted artifact itself, and the code that produced each submitted number, are kept unchanged in
`archive/submitted_artifact/` (see its `PROVENANCE.md` for discrepancies D1-D5 in detail).
- **The simplified evaluation implementation.** It produced the submitted Tables III-V and VII: a
  two-edge graph, greedy delete-and-resimulate, and a parser that silently dropped measurement, reset
  and conditioned operations. It is not the method of Sec. III. Only its corpus loader is kept, in
  `selection/`, because it defines the paper's 161-circuit set.
- **The submitted Table VI.** Its driver and circuit list were not preserved, so it cannot be
  regenerated. It is replaced by the pre-registered ablation.
- **`SemanticPreservation_v2.thy`.** Two of its global axioms are unsound, and its `project` function
  is the naive slice. It is replaced by `isabelle/QSliceSoundness.thy`.

## Known limitations of the results here
- **Four-edge slicer:** its causal slice is unsound on 5 of 962 pairs, all with mid-circuit
  measurement. When the criterion qubit is measured, `backward_slice` starts only from the
  measurement node.
- **Method prototype:** its control-edge construction is defective under qiskit 2.3.0. The primary
  configuration patches only that method (`experiments/method_eval/control_fix.py`). The unchanged
  prototype differs on 4 pairs (`experiments/results/method_secondary/`).
- **Excluded circuits:**
  - `vqe_uccsd_n4` does not parse;
  - `grover_n10` and `grover_n14` exceed 220 instructions after decomposition (Deviation 1);
  - `dqc_qft_14` needs more than 4096 measurement branches (ablation only).
- **Exact evaluation** is limited to circuits of at most 14 qubits and 220 instructions.
- **The Isabelle theory** does not mechanize the quantum instance of its assumptions, and it does not
  cover separability pruning.
- **The hardware slices** (RQ7) came from the four-edge implementation, not from `qslice/`.

## Anonymity and integrity
- Every file's origin and SHA-256 is listed in `MANIFEST.sha256.tsv`.
- Copied code is byte-identical to its source.
- The only change to data is the IBM `user_id` redaction.
- Commits are by "Anonymous Authors".
- The environment-variable name `RP_RANDOM_SEED` in `selection/qasm_loader.py` is an internal
  identifier, kept to preserve byte identity.
