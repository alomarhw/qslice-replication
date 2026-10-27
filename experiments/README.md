# experiments/: the pre-registered study and the earlier run it extends

## The study of the paper
- `PROTOCOL_ICPC.md` is the protocol, committed before the runs, with every dated deviation (I-1 to I-19).
  A deviation made after a result says so, and its analyses are reported as exploratory.
- `icpc/` holds the drivers for RQ1 to RQ4, the static slicer's acceptance runs, `make_numbers.py`, which
  computes every number of the paper from the result files, and `make_result_figs.py`, which writes the
  sources of Figs. 4 to 6. The repository README lists the order in which the drivers run.
- `common/` holds the independent oracle (`oracle.py`), the corpus loader (`corpus.py`) and the shared
  evaluation helpers (`evaluate.py`). The oracle branches exactly over mid-circuit measurements, resets and
  conditioned operations and returns each qubit's reduced density matrix. `tests/test_oracle.py` and
  `tests/test_oracle_icpc.py` check it against Qiskit's statevector simulation.
- `slicers/` holds the slicers the study compares (`registry.py`) and the QPDG baseline (`yuzhao.py`, whose
  header logs every interpretation choice).
- `bugs4q/` holds the ported Bugs4Q bugs and their triage (`triage.csv`, `TRIAGE.md`), `families/` the
  generator of the circuits with known structure, and `tests/dependence_catalogue.py` the hand-derived
  catalog of dependence cases.
- `results/icpc/` holds every result file the paper reads (`numbers.json` maps each macro to its source),
  and `logs/icpc/` the log of every run. `results/llm/` holds the language-model tasks of the protocol,
  which the paper does not report.

**Corpus A** is the 161 circuits that `../selection/qasm_loader.py` selects (at most 14 qubits, at most
220 operations, at most 80 per suite), loaded with `qiskit.qasm2` and with every qubit as a criterion.
Three are excluded, leaving 158 circuits and 784 pairs: `vqe_uccsd_n4` does not parse, and `grover_n10`
and `grover_n14` exceed 220 instructions after preparation. Preparation drops barriers and terminal
measurements and decomposes gates wider than 8 qubits.

## The earlier run
`PROTOCOL_ICPC.md` extends the protocol of an earlier run of this study, whose results it reuses, so its
hypotheses H1 and H2 were known when it was written. That run is kept here with its own protocol and
results, unchanged:
- `PROTOCOL.md` (experiments 1 and 2), `PROTOCOL_RQ5.md` (experiment 3) and `DEVIATIONS.md` (one change,
  made before any result); `PROTOCOL_HISTORY.txt` is the commit timeline and `logs/` the run logs;
- experiment 1, an ablation of the edge types of a four-edge slicer (`rq4_ablation_rerun/run.py` with
  `../fouredge/src`, corpus A and the 19 dynamic VeriQBench circuits; `results/rq4_ablation/`);
- experiment 2, the soundness, size and forward completeness of an earlier typed dependence graph
  (`method_eval/run.py` with `../qslice/qdg.py`, corpus A; `results/method_primary/` with the control-edge
  fix of `method_eval/control_fix.py`, and `results/method_secondary/` without it);
- experiment 3, its scalability (`rq5_scalability/run.py`; `results/rq5_scalability/`).

Paths in these protocols refer to the layout used when they were frozen: `reported_results/rq4_ablation/src`
is `../fouredge/src`, `described_method/` is `../qslice/`, and `reported_results/rq1_rq3_rq5/qasm_loader.py`
is `../selection/qasm_loader.py`. The drivers are unchanged, and only `run_all.sh`'s paths were updated.

`regenerate.py` re-runs experiments 1 and 2 in a scratch copy and compares the outputs with `results/`
byte for byte (about 15 minutes); `--with-rq5` adds experiment 3, which needs the full QASMBench from
`../fetch_data.py` (about 45 minutes) and is compared on its deterministic columns.
