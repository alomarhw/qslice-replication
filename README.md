> **Anonymized replication package** for double-blind review. All author and affiliation identifiers
> have been removed.

# Entanglement-Aware Quantum Program Slicing: replication package

This repository contains the implementations of the slicer, the pre-registered experiments that
produce every result in the evaluation, and a machine-checked soundness theorem. Every result
regenerates from one script. `PROVENANCE.md` maps each table and figure to the code and result files
that produce it, and explains how this package differs from the originally submitted artifact.

## Layout
```
qslice/        the method of Sec. III: typed dependence graph, entanglement-pruned slicing
               (causal cone + mutual-information nomination + exact reduced-state check), baselines
               qslice/beta_run/: the archived run behind the beta manuscript (242 circuits)
fouredge/src/  the four-edge typed QPDG (UED/ED/MD/CD) used for the edge-type ablation and Fig. 1
selection/     corpus loader that defines the paper's circuit sets
experiments/   pre-registered protocols, exact oracle, drivers, results, run logs  (RQ1-RQ5)
isabelle/      soundness of causal-cone slicing, no sorry, no axioms            (RQ6)
hardware/      captured IBM Quantum jobs and the TVD recomputation              (RQ7)
figures/       Figs. 1-5 with the scripts that generate them
data/          benchmark circuits (MQT Bench, VeriQBench, QASMBench in-cap subset); fetch_data.py
archive/       the originally submitted artifact, the code behind each submitted number, and its
               provenance notes (self-contained; see archive/README.md)
```

## Results at a glance

| RQ | Result (details in `experiments/README.md`) |
|---|---|
| RQ1 soundness | QPDG invalid on 0 of 784 (circuit, criterion) pairs; naive def-use port invalid on 27.6% (exact McNemar p = 1.9e-65) |
| RQ2 precision | QPDG slices are 23% smaller than the sound causal cone (0.540 vs 0.704 of operations; Wilcoxon p = 7.1e-80) |
| RQ3 forward | forward completeness QPDG 1.000, naive 0.988 (17 incomplete pairs) |
| RQ4 ablation | dSVR when removing ED 0.535, MD 0.129, UED 0.128, CD 0.043 (962 pairs); on dynamic circuits MD 0.481 is largest |
| RQ5 scalability | graph built for 993 of 1,062 parsable circuits (up to 151 qubits; median 28 ms); end-to-end pruned slicing median 43 ms per circuit, peak memory at most 214 MB |
| RQ6 proof | causal-cone slicing preserves the criterion's reduced state (Isabelle/HOL, from two locale assumptions shown satisfiable) |
| RQ7 hardware | 16 of 18 slices within TVD 0.05 of the full circuit on `ibm_cleveland` |

## Reproduce
```bash
bash reproduce.sh           # everything (downloads QASMBench at its pinned commit; RQ5 takes ~45 min)
bash reproduce.sh --quick   # everything except the QASMBench download and RQ5 (~20 min)
```

The script:
1. creates pinned environments (`experiments/requirements.lock`: Python 3.12, qiskit 2.3.0,
   numpy 1.26.4);
2. verifies every corpus file against `MANIFEST.sha256.tsv`;
3. runs the oracle tests;
4. reruns the experiments and compares with the shipped results: RQ1-RQ4 byte for byte, RQ5 on its
   deterministic columns;
5. recomputes the hardware table;
6. builds the Isabelle theory, if `isabelle` is on the PATH;
7. regenerates the figures into `figures/out/`.

Nothing shipped is overwritten.
