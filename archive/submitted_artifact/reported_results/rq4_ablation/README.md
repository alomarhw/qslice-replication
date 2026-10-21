# rq4_ablation/ — edge-type ablation (Table VI, Fig. 2)

**Status: the submitted Table VI is not reproducible. It is replaced by a pre-registered re-run of this
implementation in `../../corrected_results/` (results/rq4_ablation, figures/fig2_ablation_rerun.png).**

Table VI reports, for 34 circuits including dynamic circuits, the increase in soundness-violation rate
when each typed edge set is removed: ED 0.588 (20/34), MD 0.382 (13/34), UED 0.294 (10/34), CD 0.000
(0/34). It was computed with the four-edge implementation in `src/`, using a driver that ran the ablation
on the circuits that completed within the run (larger dynamic circuits stalled). That driver, its list
of 34 circuits, and its per-circuit output were not saved. Only the resulting table was kept
(`reported/TAB_ablation.csv`, identical to the submitted copy).

We do not include a reconstructed driver: without the circuit list, any subset chosen to match the
reported counts would be fitted to the answer rather than a reproduction.

Contents:

- `src/`: the four-edge typed-QPDG implementation, byte-identical: `qdg.py` (UED, ED, MD, CD edges),
  `slicer.py` (slicer variants `QDG-no-ED`, `QDG-no-MD`, `QDG-no-UED`, `QDG-no-CD`), `ablation.py`
  (SVR and delta-SVR per removed edge type), `simulate.py`, `metrics.py`, `circuit_loader.py`.
- `archived_69_circuits/`: an earlier, complete run of the same implementation on 69 circuits from a
  different corpus (QASMBench and OpenQASM 3 examples; see `run_metadata.json`), June 23, 2026,
  byte-identical. `per_circuit_results.json` has the per-circuit TVD of every variant.
- `reported/TAB_ablation.csv`: the table as submitted.

The archived run shows the same ordering as Table VI but different values:

| Removed edge type | archived run (69 circuits, TVD > 0.05) | Table VI (34 circuits) |
|---|---|---|
| ED | 36/69 = 0.522 | 20/34 = 0.588 |
| MD | 26/69 = 0.377 | 13/34 = 0.382 |
| UED | 26/69 = 0.377 | 10/34 = 0.294 |
| CD | 0/69 = 0.000 | 0/34 = 0.000 |

Under the archived run's own empirical soundness threshold (`archived_69_circuits/results.json`), the
full slicer itself has SVR 0.275, not 0, and delta-SVR is ED 0.536, MD 0.348, UED 0.348, CD 0.014.
Table VI instead reports the full slicer at SVR 0.
