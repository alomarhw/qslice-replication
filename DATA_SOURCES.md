# Data sources

These are the corpora the experiments read. Their license texts are in `data/LICENSES/`.
Per-file SHA-256s are in `MANIFEST.sha256.tsv` (shipped files) and `data/qasmbench_layout.tsv` (the
134 flattened QASMBench files).

`python fetch_data.py --verify` checks every shipped file against `MANIFEST.sha256.tsv`.

| Corpus | Upstream | Version used | License (upstream) | In this package | Used by |
|---|---|---|---|---|---|
| **QASMBench** | https://github.com/pnnl/QASMBench | commit `357b942396d5c2b7cbc1c229c585a6ef5ccaebac` (2025-01-20), pinned in `fetch_data.py` | BSD-style license of Battelle Memorial Institute (© 2020). Redistribution in source or binary form is allowed, with or without modification, if the copyright notice, the conditions and the disclaimer are kept. The Battelle name may not be used otherwise. | 39 circuits shipped in `data/qasmbench/` (all within ≤14 qubits / ≤220 operations). `fetch_data.py` downloads the full suite at the pinned commit into `data/QASMBench-master/`, and flattens 134 circuits into `data/qasmbench/`. | Corpus A (39 circuits); corpus L; the earlier run's RQ5; the scalability study S2 (medium and large sets, Deviation I-22) |
| **MQT Bench** | https://github.com/cda-tum/mqt-bench (now `munich-quantum-toolkit/bench`) | the 78 files as exported. The generator on disk was at commit `a10a74b4926826d5ac8250393dfe7bd895fc5ecd` (v2.2.2-26, 2026-06-17). Export options were not recorded, so regeneration may not be byte-identical. | MIT. Redistribution requires the copyright notice and the license text. | all 78 shipped in `data/mqtbench/` | Corpus A (42 circuits); the earlier run's RQ5 |
| **VeriQBench** | https://github.com/Veri-Q/Benchmark | the 966 files as used. The upstream commit was not recorded at the time. **Identified on 2026-10-20:** all 966 files are byte-identical (same paths) to upstream at every commit from `dc2651cacf01367ae8ffa54e4e81c0afdcc11c71` (2025-04-11) to the current HEAD `9be1083`, including `1c03e45371e5701f62c123943dec1cace4d46767` (2026-05-14, adds the LICENSE). The parent of `dc2651c` matches only 960/966. | MIT. Redistribution requires the copyright notice and the license text. | all 966 shipped in `data/veriqbench/` (combinational, dynamic, sequential, variational) | Corpus A (80 circuits); Corpus B = `veriqbench/dynamic/` (ablation); the earlier run's RQ5 |

## Hashes

The aggregate hash is the SHA-256 of the sorted `"<sha256>  <path>\n"` lines from `MANIFEST.sha256.tsv`
for that folder. A change to any file changes it.

| Folder | Files | Aggregate SHA-256 |
|---|---|---|
| `data/qasmbench/` (shipped) | 39 | `b09f1ced9adf25d61e34e36bd29574f67130388ac2d555c33db4a147a4faccfa` |
| `data/mqtbench/` | 78 | `60610f9b8cd46836dfe27e6e6e71e930511e3b9670ccf0856cf0054bb4f4a885` |
| `data/veriqbench/` | 966 | `c9090a48fd78307b504a4d154e4d77ebc1f3cb79be492a29333c0f9066e3a400` |
| `data/qasmbench_layout.tsv` (file SHA-256) | 1 | `160e5be191daefc8f9211431153018f16ec04b77c791ec1beb8ea2f66bb22193` |

## Corpus definitions (from `experiments/README.md` and `data/README.md`)
- **Corpus A** (experiments 1 and 2): `selection/qasm_loader.py` `load_corpora` keeps at most 14
  qubits, at most 220 operations and at most 80 per corpus, smallest first. That gives 161 circuits
  (QASMBench 39, MQT Bench 42, VeriQBench 80). Three are excluded, leaving 158 circuits and 784 pairs:
  - `vqe_uccsd_n4`: `qasm2` parse error;
  - `grover_n10` and `grover_n14`: more than 220 instructions after preparation (Deviation 1).
- **Corpus B** (ablation only): VeriQBench `dynamic/` circuits within the same caps, not already in A.
  That is 19 circuits and 178 pairs; `dqc_qft_14` is excluded because it needs more than 4096 branches.
- **RQ5 of the earlier run**: 1,124 circuits, reselected by the earlier protocol's rules and checked row
  by row (`experiments/rq5_scalability/`).

## LintQ's public data (Deviation I-22)
`data/lintq_artifact/` holds the inspection CSVs and the SARIF warnings of LintQ (https://github.com/sola-st/LintQ,
commit in `data/lintq_artifact/COMMIT`, MIT licence in `data/lintq_artifact/LICENSE`), read as data by
`experiments/icpc/lintq_compare.py`; LintQ itself is never run. The corpus they refer to is LintQ's
`exp_v08/files_selected` (7,568 files), downloaded from LintQ's Zenodo record and read, never executed, by the
static slicer.

