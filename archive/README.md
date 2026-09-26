# archive/: the originally submitted artifact and its provenance

`submitted_artifact/` is self-contained, with its own `data/`, `reproduce.sh` and `MANIFEST.sha256.tsv`.
It documents what the reviewers originally received and where each submitted number came from:
- `submitted_snapshot/`: the artifact exactly as reviewed (July 7, 2026). The only change is that
  the IBM `user_id` is redacted.
- `reported_results/`: the code that produced each submitted table, with regenerate scripts.
  - Submitted Tables III-V regenerate byte-identically from it.
  - Table VII regenerates structurally.
  - Table IX regenerates with the same content.
  - The submitted Table VI cannot be regenerated: its driver was not preserved.
- `PROVENANCE.md`: maps every submitted table and figure to its code, and lists discrepancies D1-D5.
- `described_method/beta_run/`: the run behind the beta manuscript (242 circuits, 1,356 slices).

The current results of the paper are in the repository root (`../README.md`). This folder is kept so
that every change from the submitted artifact can be checked.

```bash
cd submitted_artifact && bash reproduce.sh --quick
```
