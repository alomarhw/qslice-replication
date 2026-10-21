# rq1_rq3_rq5/: evaluation code for Tables III, IV, V, VII and Fig. 3

These are the files that produced the reported RQ1-RQ3 and RQ5 numbers, byte-identical to the
submitted artifact. The artifact matches the evaluation workspace at commit `dc6ebc1` except for
anonymized docstrings. The numbers were first generated at commit `12aef00` (June 29, 2026), whose
code differs only by the class name `QDG` (renamed `QPDG`) and a docstring.

- `qdg.py`: dependence graph (state-carry and entanglement edges), `backward_slice`,
  `semantic_refine_qpdg` (greedy delete-and-resimulate, fidelity >= 0.999999), `forward_coverage`,
  and the naive and causal baselines.
- `qasm_loader.py`: OpenQASM 2 loader and corpus selection (drops `measure`, `reset`, conditioned gates).
- `main.py`: driver. Writes `results/` (TAB1, TAB_per_corpus, slice/forward records, results.json with
  the McNemar and Wilcoxon tests, run_metadata) and calls `figures_qpdg.py` for figures.
- `scripts/scalability.py`: RQ5 structural scan (Table VII, Fig. 3).
- `reported/`: the reported copies from the submitted artifact.

This is **not** the method described in Sec. III (see `../../PROVENANCE.md`, D1), and Table V's QPDG
row is 1.0 by construction (D4).

## Regenerate

```bash
pip install -r requirements.txt       # pins numpy 1.26.4; needed for byte identity
python ../../fetch_data.py            # only needed for RQ5 (full QASMBench)
python regenerate.py                  # or: python regenerate.py --skip-scalability
```

Result on Python 3.12 with numpy 1.26.4 (checked while building this package):

| File | Result |
|---|---|
| `TAB1.csv` (Tables III-V) | IDENTICAL |
| `TAB_per_corpus.csv` | IDENTICAL |
| `slice_records.csv` | IDENTICAL |
| `forward_records.csv` | IDENTICAL |
| `run_metadata.json` | IDENTICAL |
| `results.json` (statistical tests) | same content; key order differs from the submitted copy, and the file is byte-identical to the version first generated at `12aef00` |
| `TAB_scalability.csv` (Table VII) | the `circuit, n_qubits, n_ops, entanglement_deps` columns are identical (1124 rows, same order); `qpdg_build_ms` is wall-clock time and differs per run |

With numpy 2.x the fidelity column differs by at most 4.5e-9. Every invalid flag and slice size stays
the same, but the first three CSVs are then not byte-identical.
