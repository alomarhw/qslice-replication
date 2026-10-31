# Reruns and relabels in the rewrite (branch icpc-rewrite)

The original version is tag `icpc-original-2026-10-28` (commit b3d6cdb), archived read-only with a checksummed
manifest. A rerun writes to `results/icpc/<run>__rerun-YYYYMMDD/` beside the old results, never over them, and is
logged here with its cause, script, commit, and the old and new value of every number that changed.

## 2026-10-28 relabel, no rerun
- **What.** The tool's name is srcSlice-Q in the rewrite (author decision). The label `QLine` in the `tool` column
  of `results/icpc/scale/s2_qasmbench.csv` (169 rows) and `s3_parametric.csv` (20 rows) became `srcSlice-Q`; scripts
  read and write it through `tool.TOOL_NAME`.
- **Numbers.** None changed: `make_numbers.py` regenerates `paper/numbers.tex` byte for byte equal to the archived
  one.

## 2026-10-28 rerun after Deviation I-26 (in-circuit control flow)
- **Cause.** The interpreter now slices `if_test` else branches, `while_loop`, `for_loop` and `switch` (I-26). Only
  files that call these can trace differently.
- **Script.** `experiments/icpc/rerun_controlflow_files.py` (scale_run.s1_one unchanged), on the 3 LintQ-corpus files
  and the 5 Qiskit HumanEval tasks (10 files, both sets) that call them; every other row is copied unchanged.
- **Where.** `results/icpc/scale__rerun-20261028/s1_lintq.csv`, `results/icpc/qhe__rerun-20261028/tasks.csv`,
  comparison in `results/icpc/scale__rerun-20261028/compare.json`. The old results are unchanged in place.
- **Numbers.** None of the paper's numbers changes. S1: 4,182 of 7,568 sliced, median 131 ms, median slice share
  23.5%, before and after. Qiskit HumanEval: 78 of 151 traced and the slice shares are unchanged; the median time
  moved from 114.6 ms to 113.8 ms (standard set) because the 10 files were timed again, which is timing noise, and
  the paper keeps the archived value.

## 2026-10-29 rerun after the gate-table correction (Deviation I-27)
- **Cause.** Five QuantumCircuit methods that take qubits but add no operation left the role table of E1 (73 -> 68
  methods). Only files that call them can trace differently.
- **Script.** `experiments/icpc/rerun_gate_table.py` (scale_run.s1_one unchanged). One file of LintQ's corpus calls
  them, `transpiled_stabilizer_test_7be7ce.py` (`circ.qubit_duration()`).
- **Where.** `results/icpc/scale__rerun-20261029/` (s1_lintq.csv, compare.json); the old results are unchanged.
- **Numbers.** The table size macro `ToolGateTable` changes from 73 to 68. That file's trace loses one spurious
  operation (24 -> 23 operations) and its slices are unchanged (32 lines for each of its 5 qubits). No other number
  changes: 4,182 of 7,568 programs sliced, median 131 ms, median slice share 23.5%, before and after.

## 2026-10-31 rerun of S2 through srcML (OpenQASM 2 front end)
- **Cause.** OpenQASM 2 is now read through srcML: `tool/qasm_srcml.py` produces Behler et al.'s markup for the whole
  OpenQASM 2 grammar and `tool/qasm_layer.py` reads it (`tool/qasm.py` read/compact). The earlier line reader is kept
  as `qasm.read_lines`/`compact_lines`, the baseline. Only srcSlice-Q's QASMBench rows (S2) are timed again.
- **Script.** `experiments/icpc/scale_run.py s2 --tools srcSlice-Q --workers 4 --out scale__rerun-20261031`. srcSlice-Q's
  limit is 3,600 s (markup of the largest circuits takes minutes); the baselines' rows are copied unchanged from
  `results/icpc/scale/s2_qasmbench.csv` with their 600 s limit. Each row now records `t_markup` and `t_layer` apart.
- **Where.** `results/icpc/scale__rerun-20261031/s2_qasmbench.csv`. The old results are unchanged in place;
  `make_numbers.py` and `make_result_figs.py` (scale figure) read the rerun.
- **Traces.** On every circuit both read, the operation counts are equal. Three circuits the line reader accepted
  (`random_QAOA_angles_k3_N1000_p1`, `_N100_p100`, `_N10000_p1`) are rejected by the srcML front end as invalid
  OpenQASM 2, and Qiskit's loader rejects them too.
- **Numbers that changed.** ScaleQbRead 164 -> 161 (new ScaleQbRejected = 6); ScaleQbMaxQubits 10,000 -> 433 (the
  10,000-qubit circuit is one of the three invalid ones); ScaleQbReadS 59 -> 703 s (new ScaleQbMarkupS 532,
  ScaleQbLayerS 171, ScaleQbReadMin 12, ScaleQbOpsPerS 8,300); ScaleQpdgSqS 0.12 -> 1.11 s (reading through srcML);
  ScaleQpdgOver 32 -> 29; ScaleLcSqS 1.1 -> 1.2 and ScaleOneRatio 1.2 -> 1.3 (timing noise). ScaleQbAllS stays 10 s.
  Paper A uses none of these numbers.

## 2026-10-31 rerun of the S2 LightCone and QPDG baselines with the package's reference code
- **Cause.** The baselines now run on `experiments/icpc/b_reference.py`, the code the replication package ships
  (`prepare` and `lightcone_pass` for Qiskit's LightCone, `QPDG` for Yu and Zhao's graph). It builds the same graph
  with the same edges, and it gives the same slices as the code that produced the earlier rows (checked on every
  qubit of 111 circuits, and here on every circuit both runs completed), but it finds the instructions on each qubit
  from a per-qubit index instead of scanning every instruction for each pair of qubits, so the QPDG is built faster.
- **Script.** `experiments/icpc/scale_run.py s2 --tools qiskit-lightcone,qpdg --workers 4 --base scale__rerun-20261031
  --out scale__rerun-20261031b`, 600 s limit as before; srcSlice-Q's and Qiskit DAG's rows are copied from
  `scale__rerun-20261031`. Short LaTeX builds ran on the machine during the run.
- **Where.** `results/icpc/scale__rerun-20261031b/s2_qasmbench.csv`; the numbers and the scale figure read it.
- **Slices.** On all 143 circuits both LightCone runs completed and all 132 both QPDG runs completed, the slice sizes
  are equal.
- **Numbers that changed.** ScaleQpdgMaxOps 8,355 -> 57,317 operations; ScaleQpdgMaxS 531 -> 111 s; ScaleQpdgSqS
  1.11 -> 8.19 s (srcSlice-Q on that larger circuit); ScaleQpdgOver 29 -> 22 (seven circuits that hit the limit now
  finish); ScaleLcMaxS 294 -> 304 s (timing noise); ScaleLcOver 3 -> 1 (three circuits that hit the limit now stop
  early with the pass's own rejection, recorded as not applicable, and one goes the other way).

## 2026-11-01 recount of the role table's kinds (Table III)
- **Cause.** The kinds of Table III summed to 67 methods, one fewer than the role table's 68: `noop`, a Qiskit method
  that takes qubits and adds a directive, was left out of every kind. It is never sliced, like `barrier` and `delay`,
  so it is now counted with them.
- **Script.** `experiments/icpc/calls_per_kind.py --data-root <data-root>`, otherwise unchanged; output
  `results/icpc/unmodelled/calls_per_kind.json` (overwritten, the change is one method in one kind).
- **Numbers that changed.** KindSpecialN 6 -> 7. No program of LintQ's corpus calls `noop`, so every per-kind program
  count, CallsSpecial included, is unchanged.

## 2026-11-01 subject statistics (Table V) from the srcML rerun, and our runnable programs added
- **Cause.** `corpus_sizes.py` read QASMBench from the original S2 run, which used the line reader, so Table V kept the
  three circuits that are not valid OpenQASM 2 (RERUNS, 2026-10-31) while RQ3 reports the srcML rerun. It now reads
  srcSlice-Q's rows of `scale__rerun-20261031b`. Our 16 runnable programs, which RQ1 uses, get a row of their own, from
  `results/icpc/tool_acceptance/dev_checks.json`.
- **Script.** `experiments/icpc/corpus_sizes.py --data-root <data-root>`; every other entry of `corpus_sizes.json` is
  unchanged.
- **Numbers that changed.** SubjQbTraced 164 -> 161; SubjQbMaxQubits 10,000 -> 433; SubjQbMedianOps 550 -> 525. New:
  SubjDevCount 16, SubjDevTraced 16, SubjDevMinQubits 3, SubjDevMaxQubits 18, SubjDevMedianOps 40, SubjDevMaxOps
  1,842, SubjDevMedianLines 24.

## 2026-11-01 OpenQASM data added to Table V (new statistics, no changed number)
- **What.** `corpus_sizes.py` also summarizes the OpenQASM data of RQ1, by distinct contents as the RQ1 numbers are:
  the OpenQASM 2 files of the corpora (trace equal to Qiskit's circuit; qubits from their `qreg` declarations,
  operations from `qasm_srcml/equiv.csv`), the official OpenQASM 3 examples and VeriQBench's OpenQASM 3 files (traced by
  the layer), and the OpenQASM 3 that Qiskit exports (qubits from their declarations, operations from their answers).
- **New macros.** SubjOqtwo* (1,212 files, 1,127 traced, 1-489 qubits, median 247 / largest 333,654 operations),
  SubjOqthreeEx* (21, 20, 1-44, 18 / 300,000: `t1.qasm` unrolls its loops to 300,000 operations on a hardware qubit),
  SubjOqthreeVq* (94, 20, 1-13, 2 / 64), SubjOqthreeRt* (1,141, 1,141, 1-489, 230 / 31,095). No existing number changes.

## 2026-11-01 medians of the LintQ comparison computed as true medians (no rerun)
- **Cause.** `make_numbers.py` took the upper middle of an even number of values as the median for the code lines of
  the files LintQ warns in. It now uses `statistics.median` (the mean of the middle two), as for the other medians;
  the srcSlice time median is switched the same way and is unchanged (401 values).
- **Numbers that changed.** LqCodeMedian 62 -> 60.5 (88 warnings). LqReadMedian stays 8.
