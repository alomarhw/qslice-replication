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
