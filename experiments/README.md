# experiments/: pre-registered experiments (RQ1-RQ5)

Every choice below was fixed before the corresponding full run:
- `PROTOCOL.md` covers experiments 1 and 2;
- `PROTOCOL_RQ5.md` covers experiment 3;
- the one later change, made before any result existed, is in `DEVIATIONS.md`;
- `PROTOCOL_HISTORY.txt` is the commit timeline;
- `logs/` holds the run logs.

Each experiment was run once, and every output is reported as produced.

Paths in the protocols refer to the layout used when they were frozen:

| Protocol path | This repository |
|---|---|
| `reported_results/rq4_ablation/src` | `../fouredge/src` |
| `described_method/` | `../qslice/` |
| `reported_results/rq1_rq3_rq5/qasm_loader.py` | `../selection/qasm_loader.py` |

The drivers are unchanged. Only `run_all.sh`'s paths were updated.

## Common setup (`common/`)
- **Oracle (`common/oracle.py`):** exact pure-state branching over mid-circuit measurement, reset and
  `if_else`. It returns each qubit's exact reduced density matrix. A slice is **sound** iff the
  criterion's Uhlmann fidelity, slice vs full circuit, is >= 1 - 1e-6. `tests/test_oracle.py` checks
  it against Qiskit `Statevector`, teleportation, reset and measurement.
- **Corpus A:** the 161 circuits of the submitted RQ1-RQ3, loaded as written with `qiskit.qasm2`,
  with every qubit as a criterion. Three are excluded, leaving 158 circuits and 784 pairs:
  - `vqe_uccsd_n4` does not parse;
  - `grover_n10` and `grover_n14` exceed 220 instructions after preparation.
- **Corpus B:** VeriQBench dynamic circuits, 19 circuits and 178 pairs. `dqc_qft_14` is excluded
  because it needs more than 4096 branches.
- **Preparation:** drop barriers and terminal measurements; decompose gates wider than 8 qubits.

## Experiment 1: edge-type ablation (RQ4, Table VI, Fig. 2)
`rq4_ablation_rerun/run.py`, four-edge implementation (`../fouredge/src`), corpora A+B.
Results in `results/rq4_ablation/`.

| Removed edge type | dSVR, all 962 pairs | exact McNemar p | dSVR, 258 dynamic-circuit pairs |
|---|---|---|---|
| ED (entanglement) | 0.535 | 1.9e-155 | 0.399 |
| MD (measurement-collapse) | 0.129 | 3.0e-36 | 0.481 |
| UED (unitary-evolution) | 0.128 | 1.9e-37 | 0.217 |
| CD (classical-feedback) | 0.043 | 9.1e-13 | 0.159 |

The full four-edge slicer's own SVR is 0.0052: 5 pairs, all with mid-circuit measurement (`shor_n5`
q4; `bb84_n8` q0, q3, q6; `cc_n12` q11).

## Experiment 2: RQ1-RQ3 with the Sec. III method (Tables III-V)
`method_eval/run.py`, method `../qslice/qdg.py`, corpus A.
- **Primary:** `results/method_primary/`, with the control-edge patch in `method_eval/control_fix.py`.
- **Secondary:** `results/method_secondary/`, the prototype unchanged.

| Slicer (primary) | Invalid rate | Mean fidelity | Slice size | Forward completeness |
|---|---|---|---|---|
| QPDG (Sec. III method) | 0.000 | 0.99999999999754 | 0.540 | 1.000 |
| Naive classical PDG (def-use) | 0.276 | 0.865 | 0.512 | 0.988 |
| Causal classical PDG (light cone) | 0.000 | 1.000 | 0.704 | 1.000 |

- **RQ1:** QPDG vs naive, exact McNemar p = 1.9e-65 (216 discordant pairs, all favouring QPDG).
- **RQ2:** causal minus QPDG size on the 784 pairs sound under both is 0.163, 95% CI
  [0.151, 0.177]. That is a 23% relative reduction. QPDG is strictly smaller on 477 pairs. Wilcoxon
  p = 7.1e-80.
- **RQ3:** forward completeness measured against the exact influence set; naive is incomplete on
  17 pairs, McNemar p = 1.5e-5.
- **Secondary run:** differs only on 4 pairs (`qec_sm_n5` q0 and `dqc_teleportation` q2, for QPDG
  and causal), which the missing control edges make unsound.

## Experiment 3: scalability of the Sec. III implementation (RQ5, Table VII, Fig. 3)
`rq5_scalability/run.py`. Machine: Intel Xeon W-2140B, 32 GiB, 4 concurrent circuits, 120 s and
4 GiB per circuit (`results/rq5_scalability/machine.json`).
- **Structural (the 1,124 Table VII circuits, selected identically to the submitted table):**
  - 993 completed;
  - 69 reached the 4 GiB memory limit;
  - 62 cannot be parsed by `qiskit.qasm2`, because of non-standard gates such as `c3sx` or a scoping
    error. The submitted lenient parser skipped such gates. Causes are in `error_diagnosis.csv`, a
    post-run diagnostic.

  Of the 1,062 parsable circuits, 93.5% completed. QDG construction took a median of 28 ms, 95th
  percentile 9.5 s, maximum 20.8 s. The conservative entanglement edges number a median 40 per
  instruction, up to 1,660.
- **End to end (corpus A, pruned slicing for every criterion, including the mutual-information
  computation and exact verification):** 157 of 158 completed. `grover_n8` reached the 120 s limit.
  Median 43 ms per circuit, 95th percentile 1.5 s, maximum 8.0 s. Peak memory was at most 214 MB.

## Regenerate
```bash
python -m venv .venv && .venv/bin/pip install -r requirements.lock
.venv/bin/python tests/test_oracle.py
.venv/bin/python regenerate.py              # RQ1-RQ4, byte for byte (about 15 minutes)
.venv/bin/python regenerate.py --with-rq5   # also RQ5 (needs ../fetch_data.py; about 45 minutes)
```
