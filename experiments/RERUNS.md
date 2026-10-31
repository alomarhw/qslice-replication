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
