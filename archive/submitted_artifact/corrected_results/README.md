# corrected_results/: pre-registered corrected experiments

Two parts of the submitted evaluation cannot stand (see `../PROVENANCE.md`):
- Table VI's driver was not preserved (D2);
- Tables III-V were produced by a simplified implementation, not the method in Sec. III (D1, D4).

This folder replaces both with new measurements. Every choice was fixed in `PROTOCOL.md` and committed
**before** any full run. The one later change is recorded in `DEVIATIONS.md`, and was made before any
result existed. Each experiment was run once, and all outputs are reported as produced. The commit
timeline is in `PROTOCOL_HISTORY.txt`.

## Contents

| Path | What it is |
|---|---|
| `PROTOCOL.md`, `DEVIATIONS.md`, `PROTOCOL_HISTORY.txt` | pre-registration, the single deviation, commit log with timestamps |
| `common/oracle.py` | exact oracle: pure-state branching over mid-circuit measurement, reset and `if_else`; returns exact reduced states. `tests/test_oracle.py` checks it against Qiskit and teleportation |
| `common/corpus.py` | corpus A (the paper's 161 circuits, loaded as written) and corpus B (VeriQBench dynamic circuits); identical preparation for all |
| `common/evaluate.py` | slice materialisation, exact McNemar, Wilcoxon + bootstrap CI |
| `rq4_ablation_rerun/run.py` | experiment 1: edge-type ablation with the four-edge implementation (`../reported_results/rq4_ablation/src`, unchanged) |
| `method_eval/run.py`, `method_eval/control_fix.py` | experiment 2: RQ1-RQ3 with the Sec. III method (`../described_method`), primary with a documented control-edge patch, secondary unchanged |
| `run_all.sh` | runs all three once |
| `results/` | every per-pair record, summary tables, tests, exclusions |
| `figures/fig2_ablation_rerun.py`, `.png` | corrected Fig. 2 from `results/rq4_ablation` |
| `regenerate.py` | reruns everything in a scratch copy and compares every result file byte for byte |
| `requirements.lock` | exact environment (Python 3.12, qiskit 2.3.0, numpy 1.26.4, ...) |

## Common setup
- **Criteria:** every qubit.
- **Soundness:** Uhlmann fidelity of the criterion's exact reduced state, slice vs full, >= 1 - 1e-6.
- **Excluded circuits:**
  - `qasmbench/small/vqe_uccsd_n4` does not parse in `qasm2.load`;
  - `mqtbench/grover_n10` and `grover_n14` exceed 220 instructions after decomposing their wide
    oracle gate (Deviation 1);
  - `veriqbench/dynamic/qft/dqc_qft_14` needs more than 4096 measurement branches (experiment 1 only).
- **Corpus A** is therefore 158 circuits and 784 pairs. **Corpus B** is 19 dynamic circuits and 178
  pairs.

## Experiment 1: edge-type ablation (replaces Table VI and Fig. 2)
`results/rq4_ablation/TAB_ablation_rerun.csv`. Primary metric: dSVR over the 962 pairs of A+B.

| Removed edge type | dSVR, all pairs (n=962) | exact McNemar p | dSVR, dynamic-circuit pairs (n=258) |
|---|---|---|---|
| ED (entanglement) | 0.535 | 1.9e-155 | 0.399 |
| MD (measurement-collapse) | 0.129 | 3.0e-36 | 0.481 |
| UED (unitary-evolution) | 0.128 | 1.9e-37 | 0.217 |
| CD (classical-feedback) | 0.043 | 9.1e-13 | 0.159 |

- **The full slicer is not perfectly sound.** Its SVR is 0.0052: 5 of 962 pairs, all in circuits with
  mid-circuit measurement (`shor_n5` q4; `bb84_n8` q0, q3, q6; `cc_n12` q11). The likely cause is that
  when the criterion qubit is measured, `backward_slice` starts only from its measurement node, so it
  drops the operations after that measurement.
- **Compared with the submitted Table VI** (ED 0.588, MD 0.382, UED 0.294, CD 0.000, n=34):
  - ED remains by far the most necessary edge type overall;
  - MD and UED are tied rather than ordered;
  - on dynamic circuits, MD is the most necessary;
  - CD is not zero.

## Experiment 2: RQ1-RQ3 with the Sec. III method (replaces Tables III-V)
`results/method_primary/` (control-edge patch) and `results/method_secondary/` (prototype unchanged).
Corpus A: 158 circuits, 784 pairs.

| Slicer (primary run) | Invalid rate | Mean fidelity | Slice size | Forward completeness |
|---|---|---|---|---|
| QPDG (Sec. III method) | 0.000 | 0.99999999999754 | 0.540 | 1.000 |
| Naive classical PDG (def-use) | 0.276 | 0.865 | 0.512 | 0.988 |
| Causal classical PDG (light cone) | 0.000 | 1.000 | 0.704 | 1.000 |

- **RQ1:** QPDG vs naive invalid, exact McNemar: 216 discordant pairs, all favouring QPDG,
  p = 1.9e-65.
- **RQ2:** on the 784 pairs sound under both, causal minus QPDG size is 0.163, 95% CI
  [0.151, 0.177]. That is a 23% relative reduction. QPDG is strictly smaller on 477 pairs.
  Wilcoxon p = 7.1e-80.
- **RQ3:** forward completeness is now measured against the exact influence set without intersecting
  the slice with it. QPDG is 1.000, and naive is 0.988, with 17 incomplete pairs; exact McNemar
  p = 1.5e-5.
- **Per corpus:** `TAB_per_corpus_method.csv`.
- **Secondary run (prototype unchanged):** nearly identical. The only differences are 4 pairs where
  the missing control edges make the QPDG and causal slices unsound (`qec_sm_n5` q0,
  `dqc_teleportation` q2): QPDG invalid 0.0026, size 0.524.

## Experiment 3: RQ5 scalability of the Sec. III implementation (replaces Table VII and Fig. 3)
`PROTOCOL_RQ5.md`, frozen in commit `7cd658c` before the run. Driver: `rq5_scalability/run.py`.
Results: `results/rq5_scalability/`. Machine: Xeon W-2140B, 32 GiB, 4 concurrent circuits, 120 s and
4 GiB per circuit.
- **Structural (the 1,124 Table VII circuits, selection identical to the submitted table):**
  - 993 completed;
  - 69 reached the memory limit;
  - 62 cannot be parsed by `qiskit.qasm2` (causes in `error_diagnosis.csv`, a post-run diagnostic).

  That is 93.5% of parsable circuits. Build time: median 28 ms, 95th percentile 9.5 s, maximum
  20.8 s.
- **End to end (corpus A, pruned slicing for every criterion):** 157 of 158 completed (`grover_n8`
  reached 120 s). Median 43 ms per circuit, 95th percentile 1.5 s, maximum 8.0 s. Peak memory at most
  214 MB.

## Regenerate
```bash
python -m venv .venv-corrected && .venv-corrected/bin/pip install -r requirements.lock
.venv-corrected/bin/python regenerate.py        # about 15 minutes; prints IDENTICAL/DIFFERENT per file
.venv-corrected/bin/python tests/test_oracle.py # oracle checks
```
