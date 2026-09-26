# hardware/: IBM Quantum proof of concept (RQ7, Table IX, Fig. 5)

- **`run_hardware.py`** submitted the 18 jobs (SamplerV2, 4096 shots) to `ibm_cleveland`.
  - The slices it ran were computed by the four-edge implementation's `QSLICE_FULL` variant
    (`../fouredge/src`).
  - To run it: `PYTHONPATH=../fouredge python run_hardware.py ...`. This needs IBM Quantum
    credentials and device access. It documents how the jobs were produced and is not part of
    `reproduce.sh`.
- **`data/ibm_cleveland_jobs/`** holds the captured job results, byte-identical except that
  `"user_id"` in the 18 `*-info.json` files is `"REDACTED"`.
- **`scripts/recompute_hardware_tvd.py`** recomputes the per-circuit TVD table and Fig. 5 from the
  captured counts.
- **`reported/TAB_hardware_ibmq.csv`** is the table as reported.

```bash
pip install "qiskit-ibm-runtime>=0.40"    # decodes the captured results; no account needed
python regenerate.py                      # prints IDENTICAL (content; line endings differ)
```

The recomputed table has the same content as the reported copy, whose line endings were changed when
the submitted artifact was assembled. The results are descriptive: 16 of 18 circuits have a marginal
TVD below delta = 0.05 between slice and full circuit on hardware.
