# rq7_hardware/: IBM Quantum hardware proof of concept (Table IX, Fig. 5)

- `run_hardware.py`: the script that submitted the 18 jobs (SamplerV2, 4096 shots) to `ibm_cleveland`.
  It comes from the four-edge implementation and imports `src.*` from `../rq4_ablation/src/`. The
  hardware slices were therefore computed by that implementation's `QSLICE_FULL` variant, not by the
  RQ1-RQ3 evaluation code (`../../PROVENANCE.md`, D1 and D5). Running it needs IBM Quantum
  credentials and device access. It is included to document how the jobs were produced, not to be
  rerun.
- `data/ibm_cleveland_jobs/`: the captured job results. They are byte-identical, except that
  `"user_id"` in the 18 `*-info.json` files is replaced by `"REDACTED"`.
- `scripts/recompute_hardware_tvd.py`: recomputes the per-circuit TVD table from the captured counts
  (unchanged).
- `reported/TAB_hardware_ibmq.csv`: the submitted table.

## Regenerate

```bash
pip install "qiskit-ibm-runtime>=0.40"    # to decode the captured results; no account needed
python regenerate.py
```

Result: `IDENTICAL (content; line endings differ)`. The recomputed table has the same content as the
submitted copy, whose line endings were changed when the artifact was assembled. It is byte-identical
to the table as first generated on June 30, 2026.
