# LintQ's public data (read as data, never executed)

From github.com/sola-st/LintQ at the commit in `COMMIT` (MIT licence, `LICENSE`):
- `Inspection_LintQ_on_LintQ_dataset.csv`: the 345 LintQ warnings the LintQ authors inspected by hand, 216 of them
  true positives (`label_resolution = TP`), with rule, file and line;
- `Inspection_LintQ_on_Bugs4Q_dataset.csv`, `Inspection_QChecker_on_LintQ_dataset.csv`,
  `Complementarity_prior_work_on_LintQ_TPs.csv`, `Reason_code_to_text.csv`: the other inspection tables;
- `data.sarif`: every LintQ warning on its 7,568-program corpus (CodeQL 2.11.2).

The corpus files themselves are LintQ's `exp_v08/files_selected`, kept outside this package (see DATA_SOURCES.md).
`experiments/icpc/lintq_compare.py` reads these files (Deviation I-22).
