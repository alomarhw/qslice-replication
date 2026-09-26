# Entanglement-Aware Quantum Program Slicing: provenance package

This package shows which code produced each number in the submitted paper, what regenerates, and what
cannot. In `corrected_results/` it adds pre-registered experiments that replace the parts of the
evaluation that cannot stand (Tables III-VI, Fig. 2). Start with **`PROVENANCE.md`**. It maps every table and
figure to its code and status, and lists the known discrepancies between the paper and that code.

```
submitted_snapshot/            the artifact exactly as reviewed (July 7, 2026); only change: IBM user_id redacted
submitted_snapshot.README.md   what the snapshot is
reported_results/
  rq1_rq3_rq5/                 evaluation code that produced Tables III-V, VII and Fig. 3; regenerate.py
  rq4_ablation/                four-edge implementation; Table VI is NOT reproducible (see its README)
  rq6_isabelle/                the submitted Isabelle/HOL theory, unchanged
  rq7_hardware/                hardware submission script, captured IBM jobs (redacted), regenerate.py
corrected_results/             pre-registered corrected experiments (Tables III-VI, Fig. 2), regenerate.py
redrawn_figures/               new scripts that redraw Figs. 1 and 4 from their sources (original drawing scripts not saved)
described_method/             prototype of Sec. III. It did NOT produce the reported numbers
data/                          benchmark circuits as used; data/README.md gives sources and versions
fetch_data.py                  fetches QASMBench at its pinned commit; verifies every corpus file
reproduce.sh                   regenerates everything that can be regenerated and compares it
PROVENANCE.md                  table/figure -> code -> status; known discrepancies
MANIFEST.sha256.tsv            every file: source, source path, SHA-256 of source and of copy
```

## Reproduce

```bash
bash reproduce.sh            # needs Python 3.11 or 3.12, internet access for QASMBench (~165 MB)
bash reproduce.sh --quick    # skip the QASMBench download and the RQ5 scalability run
bash reproduce.sh --corrected   # additionally rerun the corrected experiments (corrected_results/)
```

The script:
1. creates a virtual environment with the pinned requirements;
2. fetches and verifies the corpora;
3. reruns the evaluation (about 4 minutes) and compares every reported RQ1-RQ3 file;
4. reruns the RQ5 scalability scan (about 10 minutes);
5. recomputes the RQ7 hardware table from the captured jobs;
6. builds the Isabelle theory, if `isabelle` is on the PATH;
7. redraws Figs. 1 and 4 into `redrawn_figures/out/`;
8. with `--corrected`, reruns the corrected experiments (about 15 minutes, separate pinned environment)
   and compares every result file byte for byte.

Each comparison prints IDENTICAL or DIFFERENT. Nothing in the package is overwritten; all runs
happen in temporary directories.

## Integrity

Every copied file is byte-identical to its source. `MANIFEST.sha256.tsv` records the SHA-256 of both
source and copy; the two hashes differ only for the 18 `*-info.json` job files, where `user_id` was
replaced by `"REDACTED"`. Files written for this package (READMEs, `PROVENANCE.md`, the regenerate,
fetch and redraw scripts, `data/qasmbench_layout.tsv`, `reproduce.sh`) are listed as "new file".
